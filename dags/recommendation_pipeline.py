from airflow import DAG
from airflow.providers.ssh.operators.ssh import SSHOperator
from airflow.providers.ssh.hooks.ssh import SSHHook
from airflow.models import Connection
from airflow.utils.session import provide_session
from airflow.settings import Session
from datetime import datetime

# Configuration variables
host_postgres = "192.168.11.110"
host_vm = "192.168.11.120"
user_vm = "hduser"
postgres_port = "5432"
postgres_db = "book-platform-db"
postgres_user = "admin"
postgres_password = "admin"
dtable = "interaction"
outPutRaw = "book-recommendation/raw/interactions"
SPARK_SUBMIT_PATH = "/usr/local/spark/bin/spark-submit"

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
    schedule_interval='@daily',
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
        command=f'{SPARK_SUBMIT_PATH} --master yarn   --class LoadInteractions   --driver-memory 1g  /home/hduser/book-reco/target/scala-2.12/bookrecommendation_2.12-1.0.jar {host_postgres} {postgres_port} {postgres_db} {postgres_user} {postgres_password} {dtable} {outPutRaw}'
    )

    dataMerger = SSHOperator(
        task_id='dataMerger',
        ssh_hook=ssh_hook,
        command=f'{SPARK_SUBMIT_PATH} --master yarn   --class DailyDataMerger --driver-memory 1g  /home/hduser/book-reco/target/scala-2.12/bookrecommendation_2.12-1.0.jar'
    )

    extractData >> dataMerger
