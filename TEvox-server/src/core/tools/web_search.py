import os
import hashlib
import asyncio
from concurrent.futures import ThreadPoolExecutor

from browser_use import Agent, BrowserConfig, Browser

from src.base import DefaultConfig
from src.utils import get_llm


def str_to_md5(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def run_web_search(task):
    if not os.path.exists(".help"):
        os.makedirs(".help")

    answer_file = ".help/" + str_to_md5(task) + ".txt"
    if os.path.exists(answer_file):
        with open(answer_file, "r", encoding="utf-8") as file:
            answer = file.read().strip()
        return answer

    llm = get_llm(
        base_url=DefaultConfig.search_api_base,
        api_key=DefaultConfig.search_api_key,
        model_name=DefaultConfig.search_model,
    )
    answer = str(web_search(task=task, llm=llm))

    with open(".help/" + str_to_md5(task) + ".txt", "w", encoding="utf-8") as file:
        file.write(answer)

    return answer


def web_search(task, llm, use_vision=False, **kwargs):

    async def _web_search(task, llm, use_vision=False, **kwargs):
        agent = Agent(
            task=task,
            llm=llm,
            # browser=Browser(BrowserConfig(headless=True)),
            use_vision=use_vision,
            **kwargs,
        )
        return await agent.run()

    with ThreadPoolExecutor() as executor:
        future = executor.submit(
            asyncio.run, _web_search(task, llm, use_vision=False, **kwargs)
        )
        return future.result().final_result()

    # return asyncio.run(_web_search(task, llm, use_vision=False, **kwargs))


if __name__ == "__main__":
    task = "espidf v5.4 i2s document"
    # llm = get_llm(
    #     base_url=DefaultConfig.rag_api_base,
    #     api_key=DefaultConfig.rag_api_key,
    #     model_name=DefaultConfig.rag_model,
    # )
    # print(web_search(task=task, llm=llm))
    print(run_web_search(task=task))
