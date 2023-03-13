import json

# from torch.utils.data import dataset
import datasets
import os.path
from dotenv import load_dotenv
from third_party.spider.get_tables import dump_db_json_schema

load_dotenv()


class CoSQL(datasets.GeneratorBasedBuilder):
    VERSION = datasets.Version("1.0.0")

    BUILDER_CONFIGS = [
        datasets.BuilderConfig(
            name="cosql",
            version=VERSION,
            description="A Conversational Text-to-SQL Challenge Towards Cross-Domain Natural Language Interfaces to Databases",
        ),
    ]

    def __init__(self, *args, writer_batch_size=None, **kwargs):
        super().__init__(*args, writer_batch_size=writer_batch_size, **kwargs)
        self.schema_cache = dict()

    def _info(self):
        features = datasets.Features(
            {
                "query": datasets.Value("string"),
                "utterances": datasets.features.Sequence(datasets.Value("string")),
                "turn_idx": datasets.Value("int32"),
                "db_id": datasets.Value("string"),
                "db_path": datasets.Value("string"),
                "db_table_names": datasets.features.Sequence(datasets.Value("string")),
                "db_column_names": datasets.features.Sequence(
                    {
                        "table_id": datasets.Value("int32"),
                        "column_name": datasets.Value("string"),
                    }
                ),
                "db_column_types": datasets.features.Sequence(datasets.Value("string")),
                "db_primary_keys": datasets.features.Sequence({"column_id": datasets.Value("int32")}),
                "db_foreign_keys": datasets.features.Sequence(
                    {
                        "column_id": datasets.Value("int32"),
                        "other_column_id": datasets.Value("int32"),
                    }
                ),
            }
        )
        return datasets.DatasetInfo(
            description="CoSQL is a large-scale dataset for training and testing task oriented dialog agents with SQL",
            features=features,
            supervised_keys=None,
        )

    def _split_generators(self, dl_manager):
        datasets_path = os.getenv('DATASETS')

        return [
            datasets.SplitGenerator(
                name=datasets.Split.TRAIN,
                gen_kwargs={
                    "data_filepath": datasets_path + "cosql_dataset/sql_state_tracking/cosql_train.json",
                    "db_path": datasets_path + "cosql_dataset/database"
                },
            ),
        ]

    def _generate_examples(self, data_filepath, db_path):
        """Returns the examples in raw text form"""

        with open(data_filepath, encoding="utf-8") as f:
            cosql = json.load(f)

            idx = 0
            for sample in cosql:
                db_id = sample["database_id"]
                if db_id not in self.schema_cache:
                    self.schema_cache[db_id] = dump_db_json_schema(db_path + "/" + db_id + "/" + db_id + ".sqlite",
                                                                   db_id)
                schema = self.schema_cache[db_id]
                db_stuff = {
                    "db_id": db_id,
                    "db_path": db_path,
                    "db_table_names": schema["table_names_original"],
                    "db_column_names": [
                        {"table_id": table_id, "column_name": column_name}
                        for table_id, column_name in schema["column_names_original"]
                    ],
                    "db_column_types": schema["column_types"],
                    "db_primary_keys": [{"column_id": column_id} for column_id in schema["primary_keys"]],
                    "db_foreign_keys": [
                        {"column_id": column_id, "other_column_id": other_column_id}
                        for column_id, other_column_id in schema["foreign_keys"]
                    ],
                }

                yield idx, {
                    "utterances": [sample["final"]["utterance"]],
                    "query": sample["final"]["query"],
                    "turn_idx": -1,
                    **db_stuff,
                }

                idx += 1
                utterances = []
                for turn_idx, turn in enumerate(sample["interaction"]):
                    utterances.extend((utterance.strip for utterance in turn["utterance"].split(sep="|")))
                    yield idx, {
                        "utterances": list(utterances),
                        "query": turn["query"],
                        "turn_idx": turn_idx,
                        **db_stuff
                    }
                    idx += 1
