import os
import sys
from pathlib import Path
import mistune
from openai import OpenAI


GPT_CLIENT = OpenAI(
    api_key='sk-8KGtH7yH8nipxh9pOrgQn3IJLqxSdkBj',
    base_url="https://api.proxyapi.ru/openai/v1"
)

LAST_TOKENS_COMMON = 5000


ED_SUM_PROMPT = """{doc_content}

Проверь представленную выше документацию. Указана ли там итоговая сумма сметы?
Если да, то напиши итоговую сумму. Если нет напиши что документация не содержит сметы.
Ответь строго по шаблону:

# Общая информация о документе
В этом разделе напиши короткое описание содержимого документа

# Итоговая стоимость сметы
Укажи в этом разделе информацию об итоговой стоимости сметы, если в документе она присутствует, если нет, то удали этот раздел
"""

COMMON_SUM_PROMPT = """{doc_content}

Выше представлено содержание (или описание) документации прикрепленное к тендеру.
Напиши саммари по закупке – коротко, что закупается; дату и место поставки или оказания услуг по контракту; условия поставки (единоразовая, частями или по заявке), техническое задание (описание объекта закупки, список товаров/услуг, их количество и характеристики). Если есть смета, обязательно добавь её. Укажи стоимость обеспечения заявки и контракта; требования к документации и сертификаты; условия гарантии; а также важные моменты в контракте.
Ответь строго по шаблону (markdown):

# Общие сведения
Кто что закупает.
# Объект закупки (ТЗ, характеристики)
Описание закупаемых товаров или услуг.
# Дата, место и условия поставки (или оказания услуг)
Сроки, место и условия.
# Прохождение аттестации ПАО «Россети»
Требуется ли наличие заключения (подтверждения прохождения) аттестационной комиссии ПАО «Россети»
# Предоставление образцов
Требуется ли поставка опытных экземпляров (пробников)
# Допуск инностранного оборудования
Информация оо ограничениях к поставке иностранного обуродования или преимуществах для в поставке отчечественного оборудования.
# Смета
Если есть, укажи итоговую сумму сметы – если нет, удали этот раздел.
# Обеспечение заявки и контракта
Информация об обеспечении.
# Требуемая документация и сертификаты
Перечисли документы.
# Гарантийные обязательства
Условия гарантии.
# На что обратить внимание
Важные моменты в условиях контракта.
"""


def md_to_html(md_path: Path):
    html = mistune.html(md_path.read_text(encoding="utf-8"))
    out = md_path.with_suffix('.html')
    out.write_text(html, encoding="utf-8")


def summarize_tender(tender_dir: Path, summary_root: Path, raw_root: Path) -> None:
    """
    For each tender folder, read converted markdown files (from ED and common),
    use LLM to summarize the content and save report.md and report.html.
    """
    summary = ""
    # Process ED documents (converted to markdown)
    for doc_md in tender_dir.rglob('ed/*.md'):
        try:
            with open(doc_md, encoding='utf-8') as f:
                doc_content = f.read()
            # Focus on the last part of the document (for large docs)
            start_idx = len(' '.join(doc_content.split()[-LAST_TOKENS_COMMON:]))
            last_text = doc_content[start_idx:]
            summary += f"{doc_md.name}\n"
            try:
                response = GPT_CLIENT.chat.completions.create(
                    model="gpt-4.1-mini",
                    messages=[
                        {"role": "system", "content": (
                            "Ты помощник специалиста тендерного отдела, анализируй сметную документацию. "
                            "Отвечай только в формате JSON." 
                        )},
                        {"role": "user", "content": ED_SUM_PROMPT.format(doc_content=last_text)}
                    ],
                    temperature=0.3
                )
                summary += response.choices[0].message.content + "\n---\n"
            except Exception as e:
                print(f"ED summarization error in {doc_md.name}: {str(e)}")
        except Exception as e:
            print(f"Error reading {doc_md}: {e}")
    
    # Append common documents (just append the MD content)
    for doc_md in tender_dir.rglob('common/*.md'):
        try:
            with open(doc_md, encoding='utf-8') as f:
                doc_content = f.read()
            last_text = ' '.join(doc_content.split()[-LAST_TOKENS_COMMON:])
            summary += f"{doc_md.name}\n" + last_text + "\n---\n"
        except Exception as e:
            print(f"Error reading {doc_md}: {e}")
    
    try:
        response = GPT_CLIENT.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": (
                    "Ты помощник специалиста тендерного отдела. Твои отчёты – в формате markdown."
                )},
                {"role": "user", "content": COMMON_SUM_PROMPT.format(doc_content=summary)}
            ],
            temperature=0.3
        )
        report = response.choices[0].message.content
    except Exception as e:
        print(f"Common summarization error: {str(e)}")
        report = "Ошибка генерации отчёта."
        
    rel = tender_dir.relative_to(raw_root)
    out_dir = summary_root / rel
    out_dir.mkdir(parents=True, exist_ok=True)
    
    with open(out_dir / 'report.md', 'w', encoding='utf-8') as f:
        f.write(report)
        
    # Convert markdown to HTML report
    md_to_html(out_dir / 'report.md')
    print(f"[OK] Summarized {rel}")


# 4. Парсер аргументов и запуск
if __name__ == "__main__":
    raw_root = Path("docs_md")
    summary_root = Path("summary")

    for date_dir in sorted(raw_root.iterdir()):
        if not date_dir.is_dir(): continue
        for client_dir in sorted(date_dir.iterdir()):
            if not client_dir.is_dir(): continue
            for tpl_dir in sorted(client_dir.iterdir()):
                if not tpl_dir.is_dir(): continue
                for tender_dir in sorted(tpl_dir.iterdir()):
                    if not tender_dir.is_dir(): continue
                    summarize_tender(tender_dir, summary_root, raw_root)
