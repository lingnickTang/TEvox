import os
import hashlib

from src.core.rag.doc.query.nx_query_engine import NxQueryEngine

query_engine = None
# query_engine = NxQueryEngine({"root_path": ".rag"})


def search_information(query: str):
    global query_engine
    if not query_engine:
        query_engine = NxQueryEngine({"root_path": ".rag"})
    results = []
    for textunit in query_engine.query(query, entry_limit=10, top_k=50):
        results.append(textunit.llm_content)
    return results


def str_to_md5(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def ask_help(help):
    input(f"Help: {help}")
    answer_file = ".help/" + str_to_md5(help) + ".txt"
    if not os.path.exists(answer_file):
        answer_file = ".help/" + "help.txt"

    with open(answer_file, "r", encoding="utf-8") as file:
        answer = file.read().strip()

    if answer_file == ".help/help.txt":
        with open(".help/" + str_to_md5(help) + ".txt", "w", encoding="utf-8") as file:
            file.write(answer)

    return answer


def get_feedback():
    if not os.path.exists("feedback.txt"):
        return None
    with open("feedback.txt", "r", encoding="utf-8") as file:
        answer = file.read().strip()
    if answer:
        with open("feedback.txt", "w", encoding="utf-8") as file:
            file.write("")
    return answer


# def search_information(query: str):
#     answer_file = str_to_md5(query) + ".txt"
#     input("Searching answer file: " + answer_file)
#     if not os.path.exists(answer_file):
#         answer_file = "answer.txt"

#     with open(answer_file, "r", encoding="utf-8") as file:
#         answer = file.read().strip()

#     if answer_file == "answer.txt":
#         with open(str_to_md5(query) + ".txt", "w", encoding="utf-8") as file:
#             file.write(answer)

#     return answer

if __name__ == "__main__":
    res = search_information(
        query="""INMP441 microphone and MAX98357A amplifier I2S configuration parameters for ESP32-S3: clock polarity (idle level), LRCK/SCK frequency/rates, data format (bits-per-sample), master/slave mode requirements, and compatible framing settings""",
    )
    print(len(res))
