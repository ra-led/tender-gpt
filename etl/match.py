import os
import glob
import json
import pandas as pd
from openai import OpenAI
from tqdm import tqdm

# 1) Initialize your OpenAI client
GPT_CLIENT = OpenAI(
    api_key='sk-8KGtH7yH8nipxh9pOrgQn3IJLqxSdkBj',
    base_url='https://api.proxyapi.ru/openai/v1'
)

def check_tender_compliance(tender_desc: str,
                            lots: str,
                            supplier_desc: str,
                            anti_supplier_desc: str) -> dict:
    """
    Calls GPT to decide if a tender (description + lots) is relevant to the supplier,
    also passing the anti_supplier snippet so GPT can exclude unwanted topics.
    Returns {"compliant": bool, "reason": str}.
    """
    prompt = f"""
Analyze whether this tender matches the supplier's specialization.
Tender Description:
{tender_desc}

Lots:
{lots}

Supplier's Specialization:
{supplier_desc}

Exclude any tenders related to:
{anti_supplier_desc}

Respond in JSON:
{{"compliant": boolean, "reason": "short explanation"}}.
    """.strip()

    try:
        resp = GPT_CLIENT.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                  "role": "system",
                  "content": "You are a procurement compliance analyst. You must answer with valid JSON."
                },
                {
                  "role": "user",
                  "content": prompt
                }
            ],
            response_format={"type": "json_object"}
        )
        result = resp.choices[0].message.content
        # If it's already a dict (depends on client), skip json.loads
        if isinstance(result, str):
            result = json.loads(result)
        compliant = bool(result.get("compliant", False))
        reason = result.get("reason", "")[:500]
        return {"compliant": compliant, "reason": reason}

    except Exception as e:
        # On error, decide: default to non-compliant or compliant?
        # Here we default to non-compliant to be safe.
        return {"compliant": False, "reason": f"Error during compliance check: {e}"}


def main():
    # 2) Load your config.json
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)

    for client in cfg.get("clients", []):
        client_id = client["client_id"]
        template_id = client["template_id"]
        supplier_desc = client["supplier_description"]
        anti_supplier_desc = client.get("anti_supplier_description", "")
        print('Start', client_id, template_id)

        # 3) Find all client_data files for this client
        pattern = f"client_data_*_{client_id}_{template_id}.csv"
        for filepath in glob.glob(pattern):
            filename = os.path.basename(filepath)
            # Extract date from filename: client_data_{date}_{cid}_{tid}.csv
            parts = filename.split("_")
            # parts = ["client", "data", "{date}", "{cid}", "{tid}.csv"]
            if len(parts) < 5:
                continue
            date = parts[2]
            outname = f"match_{date}_{client_id}_{template_id}.csv"
            negative_outname = f"dismatch_{date}_{client_id}_{template_id}.csv"

            # 4) Read the data
            df = pd.read_csv(filepath, dtype={'tender_id': str})

            # ensure we have required columns
            if "description" not in df.columns or "lots" not in df.columns:
                print(f"Skipping {filepath} – missing description/lots columns.")
                continue

            # 5) Iterate rows and check
            results = []
            negative_results = []
            for idx, row in tqdm(list(df.iterrows())):
                desc = str(row["description"])
                lots = str(row["lots"])
                chk = check_tender_compliance(desc, lots, supplier_desc, anti_supplier_desc)
                row_data = row.to_dict()
                row_data["_ai_reason"] = chk["reason"]
                
                if chk["compliant"]:
                    results.append(row_data)
                else:
                    negative_results.append(row_data)

            # 6) Write matched subset
            if results:
                out_df = pd.DataFrame(results)
                out_df.to_csv(outname, index=False, encoding="utf-8-sig")
                print(f"Saved {len(out_df)} matches to {outname}")
            else:
                print(f"No matches found for {filename}")
            # 7) Write dismatched subset
            if negative_results:
                out_df = pd.DataFrame(negative_results)
                out_df.to_csv(negative_outname, index=False, encoding="utf-8-sig")

if __name__ == "__main__":
    main()