from sqlalchemy import create_engine
from dotenv import load_dotenv
import pandas as pd
import os


# Cargar credenciales del archivo .env
load_dotenv()


# Funciones auxiliares
def get_paths(file_name: str) -> str:
    # Definimos la ruta principal
    folder_path = os.getcwd()
    # Definimos la ruta del archivo
    file_path = os.path.join(folder_path, 'documents', file_name)
    # Terminamos la función regresando el path del archivo
    return file_path


def upload_data(df: pd.DataFrame, db_user: str, db_user_password: str, db_host: str, db_port: int,
                db_name: str) -> None:
    # Creamos la conexión
    engine = create_engine(f"mysql+pymysql://{db_user}:{db_user_password}@{db_host}:{db_port}/{db_name}")
    # Agregamos el dataframe a la base de datos
    df.to_sql('data', con=engine, if_exists='append', index=False)
    # Terminamos la función
    return


# Función de procesado
def proces_data(file_path: str) -> pd.DataFrame:
    # Leemos el archivo
    df = pd.read_excel(file_path)
    # Definimos las columnas que se quedan fijas (identificadores)
    static_columns = ['Agency', 'Metrica', 'Service', 'Delegation']
    # Función melt, dividimos el nombre y el valor en usd
    df_large = df.melt(id_vars=static_columns, var_name='temp_fecha', value_name='usd')
    # Forazamos formatos
    df_large['temp_fecha'] = pd.to_datetime(df_large['temp_fecha'], format='%b-%y', errors='coerce')
    # Extraemos el año
    df_large['year'] = df_large['temp_fecha'].dt.year.astype(str)
    # Extraemos el mes
    df_large['month'] = df_large['temp_fecha'].dt.month_name()
    # Renombramos las columnas
    rename_dict = {'Agency': 'agency', 'Metrica': 'metric', 'Service': 'service', 'Delegation': 'delegation'}
    df_final = df_large.rename(columns=rename_dict)
    # Hacemos el pivot
    df_pivot = df_final.pivot_table(index=['agency', 'service', 'delegation', 'year', 'month'],
        columns='metric', values='usd', aggfunc='first').reset_index()
    # Limpieza de columnas
    df_pivot.columns.name = None
    df_pivot = df_pivot.rename(columns={'Income': 'income', 'Pax': 'pax'})
    # Seleccionamos las columnas finales
    final_columns = ['agency', 'service', 'delegation', 'year', 'month', 'income', 'pax']
    df_final = df_pivot[final_columns]
    # Terminamos la funcion regresando la data procesada
    return df_final


# Función main
def main(file_name: str, db_user: str, db_user_password: str, db_host: str, db_port: int, db_name: str) -> None:
    # Obtenemos el path del archivo
    file_path = get_paths(file_name)
    # Procesamos el archivo
    df = proces_data(file_path)
    # Subimos la data
    upload_data(df, db_user, db_user_password, db_host, db_port, db_name)
    # Terminamos la función
    return

# Ejecución main
if __name__ == '__main__':
    # Variables
    FILE_NAME = 'Budget histórico 22 26.xlsx'
    DB_USER = os.getenv('DB_USER')
    DB_USER_PASSWORD = os.getenv('DB_PASSWORD')
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT')
    DB_NAME = os.getenv('DB_NAME')
    # Llamamos a la funcion main
    main(FILE_NAME, DB_USER, DB_USER_PASSWORD, DB_HOST, DB_PORT, DB_NAME)