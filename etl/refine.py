import json
import shutil
import argparse
from pathlib import Path
from typing import List

from openai import OpenAI

# ─── Configuration ─────────────────────────────────────────────────────────────

GPT_CLIENT = OpenAI(
    api_key='sk-8KGtH7yH8nipxh9pOrgQn3IJLqxSdkBj',
    base_url="https://api.proxyapi.ru/openai/v1"
)
MODEL_NAME = "gpt-4o-mini"
TEMPERATURE = 0.3

# ─── Core refine function ──────────────────────────────────────────────────────

def refine_docs_selection(
    folder: Path,
    max_docs: int,
    high_priority_keywords: List[str],
    description: str
) -> None:
    files = list(folder.glob("*"))
    if len(files) <= max_docs:
        return

    # Build the prompt
    filenames = [f.name for f in files]
    prompt = "Given the following list of document filenames:\n"
    for i, name in enumerate(filenames):
        prompt += f"{i}: {name}\n"
    prompt += (
        f"\nSelect the top {max_docs} files that best describe {description}. "
        f"Prioritize documents whose names look like any of the following examples: "
        f"{', '.join(high_priority_keywords)}. "
        "Respond with a JSON list of the selected 0-based indexes "
        '(for example: {"selected": [0, 2, 3]} ).'
    )

    try:
        resp = GPT_CLIENT.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert document classifier. "
                        "Choose the most informative file names given a set of keywords."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=TEMPERATURE
        )
        print(resp.choices[0].message.content)
        idxs = json.loads(resp.choices[0].message.content)["selected"]
        if not isinstance(idxs, list):
            raise ValueError("ChatGPT did not return a JSON list")
        selected = set(int(i) for i in idxs)
    except Exception as e:
        print(f"[WARN] GPT classification failed: {e}. Falling back to first {max_docs}.")
        selected = set(range(max_docs))

    # remove unselected files
    for i, f in enumerate(files):
        if i not in selected:
            try:
                f.unlink()
                print(f"[REMOVE] {f}")
            except OSError as e:
                print(f"[ERROR] could not remove {f}: {e}")

# ─── Driver / CLI ──────────────────────────────────────────────────────────────

def main():

    max_common = 5
    max_ed = 5

    src_root = Path('docs_clean')
    dst_root = Path('docs_refined')

    for date_dir in sorted(src_root.iterdir()):
        if not date_dir.is_dir(): continue
        for client_dir in sorted(date_dir.iterdir()):
            if not client_dir.is_dir(): continue
            for tpl_dir in sorted(client_dir.iterdir()):
                if not tpl_dir.is_dir(): continue
                for tender_dir in sorted(tpl_dir.iterdir()):
                    if not tender_dir.is_dir(): continue

                    rel = tender_dir.relative_to(src_root)
                    target_dir = dst_root / rel
                    target_dir.mkdir(parents=True, exist_ok=True)

                    # copy everything first
                    shutil.copytree(tender_dir, target_dir, dirs_exist_ok=True)

                    # run refine on subfolders
                    common = target_dir / "common"
                    if common.exists():
                        refine_docs_selection(
                            common,
                            max_docs=max_common,
                            high_priority_keywords=[
                                "Проект контракта",
                                "Техническое задание",
                                "Описание объекта закупки"
                            ],
                            description="contract conditions documents"
                        )

                    ed = target_dir / "ed"
                    if ed.exists():
                        refine_docs_selection(
                            ed,
                            max_docs=max_ed,
                            high_priority_keywords=[
                                "Сметный расчет",
                                "Локальный сметный расчет",
                                "ЛСР"
                            ],
                            description="estimate documentation"
                        )

    print("✅ Refinement complete.")

if __name__ == "__main__":
    main()