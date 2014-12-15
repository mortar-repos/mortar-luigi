# Copyright (c) 2014 Mortar Data
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

import abc
import json
import logging

import luigi
from luigi.contrib import redshift
from luigi.s3 import S3Client

logger = logging.getLogger('luigi-interface')


class CopyPigOutputToRedshiftTask(redshift.S3CopyToTable):
    """
    Use the .pig_schema file generated by Pig when writing out data
    to dynamically determine the columns that will be used to
    load Redshift.
    """

    # If a field name has aliases prepended to its name,
    # take the pig_alias_depth innermost aliases and prepend 
    # them to the column name.  Ignore the rest.
    # e.g. table_2::table_1::my_alias => table_1_my_alias if
    # pig_alias_depth is set to 1
    pig_alias_depth = luigi.IntParameter(default=1)

    @abc.abstractproperty
    def s3_schema_path(self):
        """
        Override to return the s3 path to the Pig schema file'
        """
        return None

    def table_keys(self):
        """
        Override to return a list of keys (each key in a tuple) that 
        will be appended to the columns list when creating the table.  

        Examples:

        # Primary Key on an id field:
            return [ ('PRIMARY KEY', '(id')) ]

        # Primary Key on multiple fields:
            return [ ('PRIMARY KEY', '(id1, id2, id3)') ]
        """
        return []

    def run(self):
        """
        Dynamically set columns attribute before running.
        """
        self._set_columns()
        super(CopyPigOutputToRedshiftTask, self).run()

    def _set_columns(self):
        pig_schema = self._read_schema_file()
        redshift_schema = get_column_definitions_from_pig_schema(pig_schema, alias_depth=self.pig_alias_depth)
        redshift_schema += self.table_keys()
        logger.info("Setting redshift columns as %s for table %s" % (redshift_schema, self.table))
        self.columns = redshift_schema;

    def _read_schema_file(self):
        s3Client = S3Client()
        if not s3Client.exists(self.s3_schema_path()):
            raise Exception("No schema file located at %s.  Can not set Redshift columns." % s3_schema_path)
        else:
            logger.info("Found schema file %s" % self.s3_schema_path())

        schema_key = s3Client.get_key(self.s3_schema_path())
        return schema_key.get_contents_as_string()


# Pig Type values defined here: https://github.com/apache/pig/blob/trunk/src/org/apache/pig/data/DataType.java#L60
PIG_TYPE_TO_REDSHIFT_TYPE = {
    5:  "boolean",
    10: "integer",
    15: "bigint",
    20: "float8",
    25: "float8",
    30: "timestamp",
    50: "varchar(max)",
    55: "varchar(max)",
    65: "bigint"
}

def get_column_definitions_from_pig_schema(schema, alias_depth=1):
    """
    Returns Redshift column definitions based off of the .schema file written
    out by Pig.

    @param alias_depth: If a field name has alias's prepended to its name,
                take the @alias_depth innermost aliases and prepend them to the
                column name.  Ignore the rest.
    """
    json_schema = json.loads(schema)
    fields = json_schema['fields']

    result = []
    for f in fields:
        try:
            split_name = f['name'].split("::")
            name = "_".join( split_name[ -min(alias_depth+1, len(split_name)): ])

            result.append( (name, PIG_TYPE_TO_REDSHIFT_TYPE[f['type']]) )
        except KeyError:
            raise Exception("Unsupported Pig type: %s" % f['type'])

    return result