import json

import pytest

from ican.agent.calculation import calculate
from ican.agent.configuration import trace_config
from ican.agent.schema import ToolInputError
from ican.retrieval.schema import EvidenceResult, EvidenceSource


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("5e-4*128*8/512*2", "0.002"),
        ("0.1+0.2", "0.3"),
        ("8533/1900", "4.491052631578947368421052631578947368421"),
        ("224/4/2**3", "7"),
        ("112 // 4 // 2 // 2", "7"),
        ("7 % 2", "1"),
        ("-7 // 2", "-4"),
        ("7 // -2", "-4"),
        ("-7 % 2", "1"),
        ("7 % -2", "-1"),
        ("1000000000000000000 % 3", "1"),
    ],
)
def test_decimal_calculator(expression, expected):
    assert calculate(expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os')",
        "2**10000",
        "1/0",
        "1//0",
        "1%0",
        "1.5//2",
        "1%0.5",
        "True+1",
        "[1,2]",
        "1e999",
        "1e-1000000",
        "a.b",
        "2**0.5",
        "1+" * 200,
    ],
)
def test_calculator_rejects_code_undefined_and_excessive_arithmetic(expression):
    with pytest.raises(ToolInputError):
        calculate(expression)


class ConfigCorpus:
    def __init__(self, files):
        self.files = files
        self.registry = {
            str(i): {"source_path": p, "source_type": "config"}
            for i, p in enumerate(files)
            if p.endswith(".yaml")
        }

    def allowed(self, row):
        return True

    def source_text(self, path):
        if path not in self.files:
            raise ToolInputError("Missing source")
        return self.files[path]

    def at_line(self, path, line):
        return [
            EvidenceResult(
                rank=1,
                score=0,
                chunk_id=f"{path}:{line}",
                text=self.files[path].splitlines()[line - 1],
                review_required=False,
                source=EvidenceSource(
                    source_id=path,
                    source_type="code" if path.endswith(".py") else "config",
                    source_path=path,
                    source_version="fixed",
                    location={"line_start": line, "line_end": line},
                ),
            )
        ]

    def read(self, *args):
        return []


def config_corpus():
    return ConfigCorpus(
        {
            "repo/config.py": "_C.MODEL.DROP_PATH_RATE = 0.1\n_C.MODEL.SWIN.PATCH_NORM = True\n_C.MODEL.SWIN_MLP.PATCH_NORM = False\n_C.TRAIN.ACCUMULATION_STEPS = 0\n",
            "repo/configs/base.yaml": "MODEL:\n  DROP_PATH_RATE: 0.15\n",
            "repo/configs/target.yaml": "BASE: ['base.yaml']\nMODEL:\n  DROP_PATH_RATE: 0.2\n",
        }
    )


def test_config_trace_exact_branch_and_base_opts_cli_precedence():
    corpus = config_corpus()
    artifact, proof = trace_config(
        corpus,
        "target.yaml",
        "MODEL.DROP_PATH_RATE",
        ["MODEL.DROP_PATH_RATE", "0.3"],
        {},
    )
    assert artifact["final_value"] == 0.3
    assert [s["value"] for s in artifact["chain"]] == [0.1, 0.15, 0.2, 0.3]
    assert artifact["execution"] == "static_only" and proof
    artifact, _ = trace_config(corpus, "target.yaml", "MODEL.SWIN.PATCH_NORM", [], {})
    assert artifact["final_value"] is True
    assert "SWIN_MLP" not in str(artifact["chain"])
    artifact, _ = trace_config(
        corpus,
        "target.yaml",
        "TRAIN.ACCUMULATION_STEPS",
        ["TRAIN.ACCUMULATION_STEPS", "2"],
        {"accumulation_steps": 3},
    )
    assert (
        artifact["final_value"] == 3
        and artifact["chain"][-1]["stage"] == "specific_cli"
    )


def test_config_trace_cycles_unknown_paths_and_type_mismatch():
    corpus = config_corpus()
    corpus.files["repo/configs/base.yaml"] = "BASE: ['target.yaml']"
    with pytest.raises(ToolInputError, match="cycle"):
        trace_config(corpus, "target.yaml", "MODEL.DROP_PATH_RATE", [], {})
    with pytest.raises(ToolInputError, match="exactly one"):
        trace_config(corpus, "absent.yaml", "MODEL.DROP_PATH_RATE", [], {})
    with pytest.raises(ToolInputError, match="type"):
        trace_config(
            config_corpus(),
            "target.yaml",
            "MODEL.DROP_PATH_RATE",
            ["MODEL.DROP_PATH_RATE", "True"],
            {},
        )


def test_config_partial_does_not_pretend_unknown_defaults_are_executed():
    corpus = config_corpus()
    del corpus.files["repo/config.py"]
    artifact, _ = trace_config(corpus, "target.yaml", "MODEL.DROP_PATH_RATE", [], {})
    assert artifact["final_value"] == 0.2 and artifact["status"] == "partial"
    json.dumps(artifact)


def test_unverified_override_claims_are_partial_and_not_user_arguments():
    artifact, _ = trace_config(
        config_corpus(),
        "target.yaml",
        "MODEL.DROP_PATH_RATE",
        ["MODEL.DROP_PATH_RATE", "0.9"],
        {},
    )
    assert artifact["status"] == "partial"
    assert artifact["chain"][-1]["source"] == "caller_supplied_claim_requires_review"
