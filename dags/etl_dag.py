import configparser
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators import (
    CopyToRedshiftOperator,
    DataQualityOperator,
    SASValueToRedshiftOperator,
)
from airflow.operators.dummy_operator import DummyOperator
from plugins.helpers import copy_s3_keys, sas_source_code_tables_data

config = configparser.ConfigParser()
config.read("dwh.cfg")

REDSHIFT_ARN = config["CLUSTER"]["ARN"]
S3_BUCKET = config["S3"]["BUCKET"]


default_args = {
    "owner": "kene",
    "depends_on_past": False,
    "start_date": datetime(2020, 3, 25),
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
    "catchup": False,
    "email_on_retry": False,
}


dag = DAG(
    "etl_dag",
    default_args=default_args,
    description="Load and transform data withAirflow",
)

start_operator = DummyOperator(task_id="Begin_execution", dag=dag)
end_operator = DummyOperator(task_id="Stop_execution", dag=dag)


for table in copy_s3_keys:
    copy_table_from_s3 = CopyToRedshiftOperator(
        task_id=f'copy_{table["name"]}_from_s3',
        dag=dag,
        aws_credentials_id="aws_credentials",
        redshift_conn_id="redshift",
        role_arn=REDSHIFT_ARN,
        table=table["name"],
        s3_bucket=S3_BUCKET,
        s3_key=table["key"],
        file_format=table["file_format"],
        delimiter=table["sep"],
    )

    quality_check_table = DataQualityOperator(
        task_id=f'quality_check_{table["name"]}_table',
        dag=dag,
        redshift_conn_id="redshift",
        table=table["name"],
        dq_checks=table["dq_checks"],
    )

    start_operator >> copy_table_from_s3
    copy_table_from_s3 >> quality_check_table
    quality_check_table >> end_operator


for table in sas_source_code_tables_data:
    load_table_from_sas_source_code = SASValueToRedshiftOperator(
        task_id=f'load_{table["name"]}_from_sas_source_code',
        dag=dag,
        aws_credentials_id="aws_credentials",
        redshift_conn_id="redshift",
        table=table["name"],
        s3_bucket=S3_BUCKET,
        s3_key="data/I94_SAS_Labels_Descriptions.SAS",
        sas_value=table["value"],
        columns=table["columns"],
    )

    quality_check_table = DataQualityOperator(
        task_id=f'quality_check_{table["name"]}_table',
        dag=dag,
        redshift_conn_id="redshift",
        table=table["name"],
        dq_checks=table["dq_checks"],
    )

    start_operator >> load_table_from_sas_source_code
    load_table_from_sas_source_code >> quality_check_table
    quality_check_table >> end_operator
