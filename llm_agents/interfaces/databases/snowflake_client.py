import re
from typing import Any, Dict

from snowflake import connector

from llm_agents.config import get_environment_variable

ACCOUNT = get_environment_variable("SNOWFLAKE_ACCOUNT")
USER = get_environment_variable("SNOWFLAKE_USER")
PASSWORD = get_environment_variable("SNOWFLAKE_PASSWORD")
ROLE = get_environment_variable("SNOWFLAKE_ROLE")
WAREHOUSE = get_environment_variable("SNOWFLAKE_WAREHOUSE")
DATABASE = get_environment_variable("SNOWFLAKE_DATABASE")

for var_env in [ACCOUNT, USER, PASSWORD, ROLE, WAREHOUSE, DATABASE]:
    assert var_env is not None


class SnowflakeQueryError(Exception):

    def __init__(self, message: str):
        super().__init__(message)


class SnowflakeClient:

    def __init__(
        self,
        user=USER,
        password=PASSWORD,
        role=ROLE,
        account=ACCOUNT,
        warehouse=WAREHOUSE,
        database=DATABASE,
    ):
        self.user = user
        self.password = password
        self.role = role
        self.account = account
        self.warehouse = warehouse
        self.database = database
        self.connection = None

    def _connect(self):
        if not self.connection:
            self.connection = connector.connect(
                user=self.user,
                role=self.role,
                password=self.password,
                account=self.account,
                warehouse=self.warehouse,
                database=self.database,
            )

    def run_query(self, query: str) -> list[tuple[Any]]:
        self._connect()

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query)
                data = cursor.fetchall()

            return data
        except connector.errors.ProgrammingError as e:
            raise SnowflakeQueryError(f"Query failed: {e}") from e

        finally:
            if self.connection:
                self.connection.close()
                self.connection = None

    def run_query_return_listdict(self, query: str) -> list[dict[str, Any]]:
        data = self.run_query(query)
        column_names = self.parse_sql_query_column_names(query)
        return self.format_sql_output_as_dict(column_names, data)

    def run_query_return_tablemkdwn(self, query: str) -> str:
        data = self.run_query(query)
        column_names = self.parse_sql_query_column_names(query)
        return self.format_sql_output_as_table_markdown(column_names, data)

    @staticmethod
    def parse_sql_query_column_names(sql_query: str):
        match = re.search(r"SELECT\s+([\s\S]+?)\s+FROM", sql_query, re.IGNORECASE)
        if not match:
            raise ValueError("Invalid SQL query format. Could not find column names.")

        columns = match.group(1).split(",")
        column_names: list[str] = []

        for col in columns:
            parts = re.split(r"\s+AS\s+", col, flags=re.IGNORECASE)
            if len(parts) > 1:
                column_names.append(parts[1].strip())
            else:
                column_names.append(parts[0].strip())
        return column_names

    @staticmethod
    def format_sql_output_as_dict(
        column_names: list[str], sql_output: list[tuple[Any]]
    ) -> list[Dict[str, Any]]:
        if (len(sql_output) > 0) and (len(column_names) != len(sql_output[0])):
            raise ValueError(
                "Error in format_sql_output_as_dict: column_names and sql_output don't match in length"
            )
        return [dict(zip(column_names, row)) for row in sql_output]

    @staticmethod
    def format_sql_output_as_table_markdown(
        column_names: list[str], sql_output: list[tuple[Any]]
    ) -> str:
        data: list[Dict[str, Any]] = SnowflakeClient.format_sql_output_as_dict(
            column_names, sql_output
        )
        if len(data) == 0:
            return ""
        headers = data[0].keys()
        # column_width: dict[str, int] = {
        #     h: max([len(h)] + [len(row[h]) for row in data]) for h in headers
        # }
        column_width = {h: len(h) for h in headers}
        header_row = "| " + " | ".join(headers) + " |"
        separator_row = (
            "| " + " | ".join(["-" * column_width[h] for h in headers]) + " |"
        )
        data_rows = [
            "| " + " | ".join(str(row[key]) for key in headers) + " |" for row in data
        ]
        markdown_table = "\n".join([header_row, separator_row] + data_rows)
        return markdown_table

    def get_schema_names(self) -> list[str]:
        self._connect()
        cursor = self.connection.cursor()
        try:
            cursor.execute("SHOW SCHEMAS")
            schemas = cursor.fetchall()
            return [schema[1] for schema in schemas]  # Returning schema names
        finally:
            cursor.close()

    def get_table_names(self, schema_name: str) -> list[str]:
        self._connect()
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"SHOW TABLES IN SCHEMA {schema_name}")
            tables = cursor.fetchall()
            return [table[1] for table in tables]  # Returning table names
        finally:
            cursor.close()

    def create_table(self, schema_name: str, table_name: str, columns: dict[str, str]):
        self._connect()
        cursor = self.connection.cursor()
        try:
            columns_str = ", ".join(
                [f"{col_name} {col_type}" for col_name, col_type in columns.items()]
            )
            create_table_query = (
                f"CREATE OR REPLACE TABLE {schema_name}.{table_name} ({columns_str})"
            )
            cursor.execute(create_table_query)
        finally:
            cursor.close()

    def clear_table(self, schema_name: str, table_name: str):
        self._connect()
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"TRUNCATE TABLE {schema_name}.{table_name}")
        finally:
            cursor.close()

    def drop_table(
        self, schema_name: str, table_name: str, raise_error_if_not_exist: bool = False
    ):
        self._connect()
        cursor = self.connection.cursor()

        statement = "DROP TABLE" if raise_error_if_not_exist else "DROP TABLE IF EXISTS"
        try:
            cursor.execute(f"{statement} {schema_name}.{table_name}")
        except Exception as e:
            raise e
        finally:
            cursor.close()

    def display_table_structure(
        self, schema_name: str, table_name: str
    ) -> tuple[str, str]:
        self._connect()
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"DESCRIBE TABLE {schema_name}.{table_name}")
            table_structure = cursor.fetchall()
            # Extract column name and type
            columns = [(col[0], col[1]) for col in table_structure]
            return columns
        finally:
            cursor.close()

    def write_values(
        self,
        schema_name: str,
        table_name: str,
        values: list[list[str]],
        overwrite: bool = True,
    ):
        if len(values[0]) == 0:
            return
        if overwrite:
            self.clear_table(schema_name, table_name)

        self._connect()
        cursor = self.connection.cursor()

        values_str = ", ".join(["%s"] * len(values[0]))
        insert_query = f"INSERT INTO {schema_name}.{table_name} VALUES ({values_str})"

        cursor.executemany(insert_query, values)
        cursor.close()

    def close(self):
        if self.connection:
            self.connection.close()
            self.connection = None


# class ParseSQLQueryOutputFunction:

#     @classmethod
#     def run(cls, sql_query: str, sql_result: SQLOutput) -> TableRows:

#         match = re.search(r"SELECT\s+([\s\S]+?)\s+FROM", sql_query, re.IGNORECASE)
#         if not match:
#             raise ValueError("Invalid SQL query format. Could not find column names.")

#         columns = match.group(1).split(",")
#         column_names: list[str] = []

#         for col in columns:
#             parts = re.split(r"\s+AS\s+", col, flags=re.IGNORECASE)
#             if len(parts) > 1:
#                 column_names.append(parts[1].strip())
#             else:
#                 column_names.append(parts[0].strip())

#         table_rows = [dict(zip(column_names, row)) for row in sql_result]

#         return table_rows
