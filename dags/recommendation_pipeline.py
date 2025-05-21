from airflow import DAG
from airflow.providers.ssh.operators.ssh import SSHOperator
from airflow.providers.ssh.hooks.ssh import SSHHook
from airflow.models import Connection
from airflow.utils.session import provide_session
from airflow.settings import Session
from datetime import datetime , timedelta

# Configuration variables
host_postgres = "192.168.11.110"
host_vm = "192.168.11.108"
user_vm = "hduser"
postgres_port = "5432"
postgres_db = "book-platform-db"
postgres_user = "admin"
postgres_password = "admin"
dtable = "interaction"
interactions_date = (datetime.today() - timedelta(days=1)).strftime('%Y/%m/%d')
redis_auth = "admin"
redis_host = "192.168.11.110"
outPutRaw = "book-recommendation/raw/interactions"
SPARK_SUBMIT_PATH = "/usr/local/spark/bin/spark-submit"
date_execution = datetime.today().strftime('%Y/%m/%d')


# Default DAG arguments
default_args = {
    'owner': 'hduser',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
}

# Create or update SSH connection
@provide_session
def create_or_update_ssh_connection(session: Session = None):
    conn_id = "ssh_default"
    existing_conn = session.query(Connection).filter(Connection.conn_id == conn_id).first()
    
    if existing_conn:
        existing_conn.host = host_vm
        existing_conn.login = user_vm
        existing_conn.conn_type = "ssh"
        existing_conn.port = 22
        print(f"Updated existing SSH connection '{conn_id}' to host {host_vm}")
    else:
        new_conn = Connection(
            conn_id=conn_id,
            conn_type="ssh",
            host=host_vm,
            login=user_vm,
            port=22
        )
        session.add(new_conn)
        print(f"Created new SSH connection '{conn_id}' to host {host_vm}")
    session.commit()

# Call the function at DAG load
create_or_update_ssh_connection()

# Define the DAG
with DAG(
    'recommendation_pipeline',
    default_args=default_args,
    description='Pipeline to export interactions to HDFS, preprocess, merge, train ALS, and write recommendations to PostgreSQL via SSH Spark on YARN',
    schedule_interval='30 1 * * *',  # tous les jours à 1h30 du matin
    start_date=datetime(2025, 4, 1),
    catchup=False,
) as dag:

    ssh_hook = SSHHook(
        ssh_conn_id='ssh_default',
        cmd_timeout=None    
    )

    extractData = SSHOperator(
        task_id='extractData',
        ssh_hook=ssh_hook,
        command=f'{SPARK_SUBMIT_PATH} --master yarn --class LoadInteractions --driver-memory 1g  /home/hduser/book-reco/target/scala-2.12/bookrecommendation_2.12-1.0.jar {host_postgres} {postgres_port} {postgres_db} {postgres_user} {postgres_password} {outPutRaw}'
    )

    dataMerger = SSHOperator(
        task_id='dataMerger',
        ssh_hook=ssh_hook,
        command=f'{SPARK_SUBMIT_PATH} --master yarn   --class DailyDataMerger --driver-memory 1g  /home/hduser/book-reco/target/scala-2.12/bookrecommendation_2.12-1.0.jar'
    )

    trainSGD = SSHOperator(
        task_id = 'trainSGD',
        ssh_hook=ssh_hook,
        command=f'cd ~/sysrd-projet && sbt clean assembly && {SPARK_SUBMIT_PATH} --class org.recommender.UltraRecommend --master local[*]  /home/hduser/sysrd-projet/target/scala-2.12/BookSGD-assembly-0.1.jar 5  hdfs://localhost:9000/book-recommendation/raw/interactions/{interactions_date}  hdfs://localhost:9000/book-recommendation/recommendations/{date_execution}'
    )

    cleanCacheRedis = SSHOperator(
        task_id = 'cleanCacheRedis',
        ssh_hook=ssh_hook,
        command=f'cd ~/book-reco && {SPARK_SUBMIT_PATH} --master local[*] --class RedisFlushAll target/scala-2.12/bookrecommendation_2.12-1.0.jar {redis_host} {redis_auth}'
    )

    putOnCache = SSHOperator(
        task_id = 'putOnCache',
        ssh_hook=ssh_hook,
        command=f'cd ~/book-reco && {SPARK_SUBMIT_PATH} --master local[*] --class BookRecommendation target/scala-2.12/bookrecommendation_2.12-1.0.jar {redis_host} {redis_auth} {host_postgres} {postgres_password} {date_execution}'
    )

    extractData >> trainSGD >> cleanCacheRedis >> putOnCache
