import os, json, csv, shutil

import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
import BaseDeDatos_Lib_v04 as bd




# 🔹 Configuración


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(BASE_DIR, "config.json")) as f:
    config = json.load(f)
    db_conf = config["database"]
    ftp_conf = config["ftp"]
    folder_conf = config["carpetas"]
    DESTINO = folder_conf['destino']
    fecha_inicial = pd.to_datetime(config["database"]["last_date"], format="%Y-%m-%d")


with open("metadata_picarro_G2401_ush.txt", "r", encoding="utf-8") as f:
    # este proceso es para seleccionar solo las columnas que esten en el archivo de metadatos.
    # ademas sirve para seleccionar cuales de ellas seran promedio, cuales solo necesito el primer valor
    # y cuales de ellas necesito calcular la mayoria.

    lineas = f.readlines()
    for linea in lineas:
        if "Descripción de variables:" in  linea:
            inicio_index = lineas.index(linea) + 1
        if "Comentarios:" in linea:
            fin_index = lineas.index(linea)
    columnas = list()
    columnas_promedio = list()
    columnas_primero = list()
    columnas_mayoria = list()
    columnas_agregar = list()
    formato_decimales = {}

    #for linea in :
    for i in range(inicio_index,fin_index):
        try:
            columnas.append(lineas[i][:lineas[i].index(":")].replace("# ", ''))
            if "primer valor" in lineas[i]:
                columnas_primero.append(lineas[i][:lineas[i].index(":")].replace("# ", ''))
            if "mayoria" in lineas[i]:
                columnas_mayoria.append(lineas[i][:lineas[i].index(":")].replace("# ", ''))
            if "promedio" in lineas[i]:
                columnas_promedio.append(lineas[i][:lineas[i].index(":")].replace("# ", ''))
            if "agregar" in lineas[i]:
                columnas_agregar.append(lineas[i][:lineas[i].index(":")].replace("# ", ''))
            if '&' in lineas[i]:
                formato_decimales[lineas[i][:lineas[i].index(":")].replace("# ", '')] = '{:.'+ str(int(lineas[i][lineas[i].index("&")+1:])) + 'f}'
            if '$' in lineas[i]:
                lineas[i] = lineas[i][:lineas[i].index('$')] + '\n'

        except:
            if '$' in lineas[i]:
                lineas[i] = lineas[i][:lineas[i].index('$')] + '\n'
            pass


# Crear motor SQLAlchemy
engine = create_engine(f"postgresql+psycopg2://{db_conf['user']}:{db_conf['password']}@{db_conf['host']}:{db_conf['port']}/{db_conf['name']}")



# Rutas absolutas
#ORIGEN =  os.path.join(FTP_DIR, folder_conf['cargado'])
#DESTINO = ORIGEN
def minute_mode(x):
    m = x.mode()
    if len(m) == 0:
        return None
    return m.iloc[0]

def aplicar_formato(columna):
    if columna.name not in formato_decimales:
        return columna

    formato = formato_decimales[columna.name]

    return columna.map(
        lambda x: formato.format(x) if pd.notna(x) else ''
    )



def procesar_archivos():
    for fecha in pd.date_range(fecha_inicial, pd.to_datetime('today'), freq='D'):
        target_dir = os.path.join(DESTINO, fecha.strftime('%Y'), )

        df_dia = bd.buscarEnBaseDeDatos(engine, db_conf['tabla'], fecha, fecha + pd.to_timedelta(arg=1, unit="D"))
        df_dia.drop(columns=['DateTime'], inplace=True)
        df_dia["DateTime"] = df_dia.index

        output_path = os.path.join(target_dir, folder_conf['nombre'] + fecha.strftime("%Y%m%d.csv"))
        # crear la carpeta si no existe
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Calculo el archivo en formato minutalmente
        df_mean = df_dia.resample('1min').agg({
            **{col: 'mean' for col in columnas_promedio},
            **{col: minute_mode for col in columnas_mayoria},
            **{col: 'first' for col in columnas_primero}
        })

        df_sd = (
            df_dia[columnas_promedio]
            .resample('1min')
            .std()
            .add_prefix('SD_')
        )
        df_n = df_dia[columnas_promedio].resample('1min').count().add_prefix('N_')
        df_n.rename(columns={df_n.columns.tolist()[-1]: 'N'}, inplace=True)

        df_dia = pd.concat([df_mean, df_sd, df_n], axis=1)

        #df_dia = df_dia.style.format(formato_decimales)
        df_dia = df_dia.apply(aplicar_formato)

        # crear el CSV temporal
        df_dia[columnas].to_csv(output_path, index=False)
        # leer el CSV temporal
        with open(output_path, "r", encoding="utf-8") as archivo:
            contenido = archivo.read()
        # sobreescribir el CSV con el encabezado
        with open(output_path, "w", encoding="utf-8") as archivo:
            archivo.write("".join(lineas) + contenido)


    config["database"]["last_date"] = (fecha - pd.Timedelta(days=1)).strftime('%Y-%m-%d')

    # Sobrescribir el archivo con la nueva información
    with open(os.path.join(BASE_DIR, "config.json"), 'w', ) as file:
        json.dump(config, file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    procesar_archivos()


