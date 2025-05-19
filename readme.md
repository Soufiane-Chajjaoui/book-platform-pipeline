# Book Recommendation System

This project implements a book recommendation system using a data pipeline that processes user interactions, trains a machine learning model, and serves personalized recommendations. The pipeline leverages PostgreSQL, Apache Airflow, Apache Spark with Scala, HDFS, and Redis, with continuous maintenance by DevOps.

## Pipeline Architecture

The pipeline processes user interactions daily, generates recommendations, and serves them to clients in Batch. Below is an overview of the workflow:

### 1. Data Ingestion
- **Client externe : Envoi des interactions** → **API Backend** → **PostgreSQL**
  - External clients send user interactions (e.g., likes, views) to the API backend.
  - The API stores these interactions in a PostgreSQL database (`book-platform-db`).
  - Tables involved:
    - `User`: Stores user information (e.g., `id`, `email`, `username`).
    - `Category`: Stores book categories (e.g., `Fiction`, `Non-Fiction`).
    - `Book`: Stores book metadata (e.g., `isbn`, `title`, `rating`).
    - `Interaction`: Stores user-book interactions (e.g., `user_id`, `book_id`, `action`, `action_date`).

### 2. Daily ETL to HDFS
- **Airflow** → **ETL** → **HDFS/raw**
  - An Airflow DAG (`generate_book_recommendations`) runs daily at 00:00 AM to orchestrate the pipeline.
  - **Step 1**: Deletes interactions for the current day from the `Interaction` table in PostgreSQL to avoid duplicates.
  - **Step 2**: Uses `LoadInteractions.scala` to extract the current day's interactions from PostgreSQL and save them to HDFS.
    - Source: PostgreSQL `Interaction` table.
    - Destination: `hdfs://localhost:9000/book-recommendation/processed/interactions/yyyy/mm/dd`.
    - Format: CSV with columns `user_id`, `isbn`, `LIKE`, `VIEW`.
  - **Step 3**: Copies the processed data to the raw directory for archival and further processing.
    - Destination: `hdfs://localhost:9000/book-recommendation/raw/interactions/yyyy/mm/dd`.

### 3. Data Preprocessing
- **Spark/Scala: Prétraitement** → **HDFS/processed**
  - **DailyDataMerger.scala** merges the current day's data with the existing `DataSet` (historical data).
    - Source: `hdfs://localhost:9000/book-recommendation/raw/interactions/yyyy/mm/dd` (today's data).
    - Existing Data: `hdfs://localhost:9000/book-recommendation/raw/interactions/DataSet` (historical data).
    - Process:
      - If `DataSet` exists, merges today's data with it and removes duplicates.
      - If `DataSet` doesn’t exist, creates it with today’s data.
    - Destination: Overwrites `hdfs://localhost:9000/book-recommendation/raw/interactions/DataSet`.

### 4. Model Training
- **Spark/Scala: Entraînement SGD** → **HDFS/model**
  - **GenerateRecommendationsMLlib.scala** (or equivalent) trains a recommendation model using Stochastic Gradient Descent (SGD) with Spark MLlib.
    - Source: `hdfs://localhost:9000/book-recommendation/raw/interactions/DataSet`.
    - Process: Trains an ALS (Alternating Least Squares) model or similar SGD-based algorithm to generate user-book recommendation scores.
    - Destination: Saves the trained model to `hdfs://localhost:9000/book-recommendation/model/`.

### 5. Recommendation Generation
- **Spark/Scala: Génération des recommandations** → **HDFS/recommendations**
  - **GenerateRecommendationsMLlib.scala** generates personalized recommendations for users.
    - Source: Trained model at `hdfs://localhost:9000/book-recommendation/model/`.
    - Input Data: `hdfs://localhost:9000/book-recommendation/raw/interactions/DataSet`.
    - Process: Uses the model to predict and rank book recommendations for each user.
    - Destination: Saves recommendations to `hdfs://localhost:9000/book-recommendation/recommendations/`.

### 6. Recommendation Serving
- **ETL** → **Redis**
  - An ETL process extracts recommendations from HDFS and loads them into Redis for fast access.
    - Source: `hdfs://localhost:9000/book-recommendation/recommendations/`.
    - Destination: Redis key-value store (e.g., keys like `user:<user_id>` with a list of recommended `isbn` values).
- **Client externe : Demande de page suivante** → **API Backend** → **Redis** → **Recommandations**
  - External clients request the next page of recommendations via the API backend.
  - The API queries Redis to fetch recommendations for the user.
  - Recommendations are returned to the client in real-time.

### 7. Maintenance
- **DevOps: Maintenance HDFS** (en continu)
  - DevOps team continuously monitors and maintains the HDFS cluster.
  - Tasks include:
    - Ensuring HDFS availability and performance.
    - Managing storage (e.g., cleaning up old data, balancing data nodes).
    - Monitoring pipeline jobs for failures or delays.

## Directory Structure in HDFS
- `hdfs://localhost:9000/book-recommendation/raw/interactions/2025/05/<day>`: Raw daily interactions.
- `hdfs://localhost:9000/book-recommendation/raw/interactions/DataSet`: Merged historical dataset.
- `hdfs://localhost:9000/book-recommendation/processed/interactions/2025/05/<day>`: Processed daily interactions.
- `hdfs://localhost:9000/book-recommendation/model/`: Trained recommendation model.
- `hdfs://localhost:9000/book-recommendation/recommendations/`: Generated recommendations.

## Technologies Used
- **PostgreSQL**: Stores user interactions and metadata.
- **Apache Airflow**: Orchestrates the daily pipeline.
- **Apache Spark with Scala**: Processes data, trains models, and generates recommendations.
- **HDFS**: Stores raw data, processed data, models, and recommendations.
- **Redis**: Serves recommendations in real-time.
- **API Backend**: Handles client requests and interactions with the database and Redis.

## Setup Instructions
1. **PostgreSQL**:
   - Initialize the database with the provided Python script (`/path/to/your_script.py`).
   - Ensure tables (`User`, `Category`, `Book`, `Interaction`) are created.
2. **HDFS**:
   - Start the HDFS cluster (`start-dfs.sh`).
   - Create base directories: `hdfs dfs -mkdir -p hdfs://localhost:9000/book-recommendation/`.
3. **Airflow**:
   - Deploy the DAG (`/home/hduser/airflow/dags/generate_recommendations_dag.py`).
   - Start the Airflow scheduler and webserver.
4. **Spark**:
   - Compile the Scala project: `cd /home/hduser/book-reco && sbt clean compile package`.
   - Ensure PostgreSQL JDBC driver (`/home/hduser/spark-jars/postgresql-42.2.6.jar`) is available.
5. **Redis**:
   - Start the Redis server and configure it for recommendation storage.

## Running the Pipeline
- Trigger the Airflow DAG manually:
  ```bash
  airflow dags trigger -e "2025-05-19T01:56:00+01:00" generate_book_recommendations
