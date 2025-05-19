import psycopg2
from faker import Faker
import random
from datetime import datetime, timedelta

# Initialize Faker for generating random data
fake = Faker()

# PostgreSQL connection parameters
db_params = {
    "host": "localhost",
    "port": "5432",
    "database": "book-platform-db",
    "user": "admin",
    "password": "admin"
}

# Function to establish connection
def get_connection():
    return psycopg2.connect(**db_params)

# Create tables
def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    # Create the "User" table (quotes to avoid SQL reserved word conflict)
    cur.execute("""
    CREATE TABLE "User" (
        id SERIAL PRIMARY KEY,
        email CHARACTER VARYING(255) NOT NULL UNIQUE,
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        password CHARACTER VARYING(255) NOT NULL,
        username CHARACTER VARYING(255) NOT NULL,
        age INTEGER,
        preferred_categories CHARACTER VARYING[] DEFAULT '{}'
    );
    """)

    # Create the "Category" table
    cur.execute("""
    CREATE TABLE Category (
        id SERIAL PRIMARY KEY,
        name CHARACTER VARYING(100) NOT NULL,
        number_of_books INTEGER DEFAULT 0
    );
    """)

    # Create the "Book" table
    cur.execute("""
    CREATE TABLE Book (
        rating_count DOUBLE PRECISION,
        category_id INTEGER,
        number_of_pages INTEGER,
        date_of_publish TIMESTAMP WITHOUT TIME ZONE,
        title CHARACTER VARYING(255) NOT NULL,
        rating DOUBLE PRECISION,
        isbn CHARACTER VARYING(13) UNIQUE,
        image CHARACTER VARYING(255),
        authors_name CHARACTER VARYING[] DEFAULT '{}',
        PRIMARY KEY (isbn)
    );
    """)

    # Create the "Interaction" table
    cur.execute("""
    CREATE TABLE Interaction (
        book_id CHARACTER VARYING NOT NULL,
        action CHARACTER VARYING(50),
        id SERIAL PRIMARY KEY,
        action_date TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES "User"(id) ON DELETE CASCADE,
        FOREIGN KEY (book_id) REFERENCES Book(isbn) ON DELETE CASCADE
    );
    """)

    # Create indexes
    cur.execute('DROP INDEX IF EXISTS idx_interactions_user_id;')
    cur.execute('DROP INDEX IF EXISTS idx_interactions_book_id;')
    cur.execute('CREATE INDEX idx_interactions_user_id ON Interaction(user_id);')
    cur.execute('CREATE INDEX idx_interactions_book_id ON Interaction(book_id);')

    conn.commit()
    cur.close()
    conn.close()

# Insert random data
def insert_random_data():
    conn = get_connection()
    cur = conn.cursor()

    # Insert users into "User"
    for _ in range(200):
        email = fake.email()
        password = "hashedpassword"
        username = fake.user_name()
        age = random.randint(18, 80)
        preferred_categories = [fake.word() for _ in range(random.randint(1, 3))]
        try:
            cur.execute("""
            INSERT INTO "User" (email, password, username, age, preferred_categories)
            VALUES (%s, %s, %s, %s, %s);
            """, (email, password, username, age, preferred_categories))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            continue
    conn.commit()

    # Insert categories into "Category"
    categories = [
        ('Fiction', 0), ('Non-Fiction', 0), ('Science-Fiction', 0),
        ('Fantasy', 0), ('Biographie', 0), ('Histoire', 0),
        ('Poésie', 0), ('Cuisine', 0), ('Voyage', 0), ('Technologie', 0)
    ]
    cur.executemany("""
    INSERT INTO Category (name, number_of_books)
    VALUES (%s, %s);
    """, categories)
    conn.commit()

    # Fetch category IDs
    cur.execute("SELECT id FROM Category;")
    category_ids = [row[0] for row in cur.fetchall()]

    # Insert books into "Book"
    for _ in range(1000):
        title = fake.sentence(nb_words=3).replace('.', '')
        isbn = fake.isbn13().replace('-', '')
        rating = round(random.uniform(0.0, 5.0), 1)
        rating_count = random.randint(0, 1000)
        number_of_pages = random.randint(50, 1000)
        date_of_publish = fake.date_time_between(start_date="-50y", end_date="now")
        image = fake.image_url()
        authors_name = [fake.name() for _ in range(random.randint(1, 3))]
        category_id = random.choice(category_ids)
        try:
            cur.execute("""
            INSERT INTO Book (rating_count, category_id, number_of_pages, date_of_publish, title, rating, isbn, image, authors_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (rating_count, category_id, number_of_pages, date_of_publish, title, rating, isbn, image, authors_name))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            continue
    conn.commit()

    # Fetch user IDs and book ISBNs
    cur.execute('SELECT id FROM "User";')
    user_ids = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT isbn FROM Book;")
    book_isbns = [row[0] for row in cur.fetchall()]

    if not user_ids:
        raise ValueError("No users were inserted.")
    if not book_isbns:
        raise ValueError("No books were inserted.")

    # Insert interactions into "Interaction"
    for _ in range(20000):
        user_id = random.choice(user_ids)
        book_id = random.choice(book_isbns)
        action = random.choice(['LIKE', 'VIEW'])
        action_date = fake.date_time_between(start_date="-1y", end_date="now")
        try:
            cur.execute("""
            INSERT INTO Interaction (book_id, action, user_id, action_date)
            VALUES (%s, %s, %s, %s);
            """, (book_id, action, user_id, action_date))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            continue
    conn.commit()
    cur.close()
    conn.close()

def insert_interactions():
    conn = get_connection()
    cur = conn.cursor()

    # Récupérer les IDs
    cur.execute('SELECT id FROM "User";')
    user_ids = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT isbn FROM Book;")
    book_isbns = [row[0] for row in cur.fetchall()]

    if not user_ids or not book_isbns:
        raise ValueError("No users or books were inserted.")

    print("Inserting interactions...")

    interactions = []
    for _ in range(20000):
        user_id = random.choice(user_ids)
        book_id = random.choice(book_isbns)
        action = random.choice(['VIEW', 'LIKE'])
        action_date = fake.date_time_between(start_date="-1y", end_date="now")
        interactions.append((book_id, action, user_id, action_date))

    # Découper en batchs de 1000 pour éviter surcharge mémoire
    batch_size = 1000
    for i in range(0, len(interactions), batch_size):
        batch = interactions[i:i+batch_size]
        cur.executemany("""
            INSERT INTO Interaction (book_id, action, user_id, action_date)
            VALUES (%s, %s, %s, %s);
        """, batch)
        conn.commit()

    cur.close()
    conn.close()
    print("Interactions inserted.")

def insert_interactions_today():
    conn = get_connection()
    cur = conn.cursor()

    # Récupérer les IDs
    cur.execute('SELECT id FROM "User";')
    user_ids = [row[0] for row in cur.fetchall()]
    cur.execute("SELECT isbn FROM Book;")
    book_isbns = [row[0] for row in cur.fetchall()]

    if not user_ids or not book_isbns:
        raise ValueError("No users or books were inserted.")

    print("Inserting today's interactions...")

    interactions = []

    today = datetime.now().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())

    for _ in range(10000):  # ou 20000 si tu veux
        user_id = random.choice(user_ids)
        book_id = random.choice(book_isbns)
        action = random.choice(['VIEW', 'LIKE'])
        action_date = fake.date_time_between(start_date=start_of_day, end_date=end_of_day)
        interactions.append((book_id, action, user_id, action_date))

    # Batch insert
    batch_size = 1000
    for i in range(0, len(interactions), batch_size):
        batch = interactions[i:i+batch_size]
        cur.executemany("""
            INSERT INTO Interaction (book_id, action, user_id, action_date)
            VALUES (%s, %s, %s, %s);
        """, batch)
        conn.commit()

    cur.close()
    conn.close()
    print("Today's interactions inserted.")

# Run script
if __name__ == "__main__":
    print("Creating tables...")
    create_tables()
    print("Inserting random data...")
    insert_random_data()
    print("Inserting daily interactions...")
    insert_interactions_today()
    print("Done!")