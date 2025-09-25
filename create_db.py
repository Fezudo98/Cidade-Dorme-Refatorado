import psycopg2

conn = psycopg2.connect(
    dbname="postgres",  # conecta primeiro no banco padrão
    user="squarecloud",
    password="rnWHcmeELQIgrGIq3qGz0Yzy",
    host="square-cloud-db-af7e4284a40b41eb8eee3ba27d6fcdbf.squareweb.app",
    port="7052",
    sslmode="verify-full",
    sslrootcert="certs/ca-certificate.crt",  # CA
    sslcert="certs/certificate.pem",         # Certificado do cliente (o PEM)
    sslkey="certs/private-key.key"           # Chave privada
)
conn.autocommit = True

cur = conn.cursor()
cur.execute("CREATE DATABASE cidade_dorme_db;")
cur.close()
conn.close()

print("Banco criado com sucesso!")
