import re
import json
import yaml
import textwrap

from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain.chains.openai_functions import create_structured_output_runnable
from langchain_community.callbacks import get_openai_callback

from src.utils.log import logger


def extract_code_block(text, keyword: str = "", extract_all: bool = False):
    """
    Extract code block(s) from markdown fenced code blocks.
    
    Args:
        text: The text containing code blocks
        keyword: Language identifier (e.g. "cpp", "yaml", "json")
        extract_all: If True, return list of all matching blocks; else return the last one
    
    Returns:
        Single string (default) or list of strings when extract_all=True
    """
    # Use non-greedy (.*?) so each block matches independently when multiple blocks exist
    pattern = f"```{keyword}[^\n]*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        stripped = [m.strip() for m in matches]
        return stripped if extract_all else stripped[-1]
    raise ValueError(f"Failed to parse regular expression {pattern}.")


def replace_json_string(text):
    pattern = r'"[^"]+":\s*"((?:\\"|.)*?)(?="\s*[,}])'
    matches = re.findall(pattern, text)
    for value in matches:
        step1 = value.replace('\\"', '"')
        step2 = step1.replace('"', '\\"')
        text = text.replace(value, step2)
    return text


def _normalize_yaml_literal_code_blocks(yaml_str: str) -> str:
    """
    Convert YAML literal blocks (code: |) into quoted strings so that C/code
    colons (e.g. case FOO:) are not parsed as YAML keys.
    """
    result = []
    i = 0
    lines = yaml_str.split("\n")
    while i < len(lines):
        line = lines[i]
        # Match "  ... code:" followed by optional space and literal block indicator
        code_key_match = re.match(r"^(\s*)code:\s*$", line)
        if code_key_match and i + 1 < len(lines):
            indent_str = code_key_match.group(1)
            indent = len(indent_str)
            next_line = lines[i + 1]
            # Literal block: | or |- or |+
            block_match = re.match(r"^(\s*)\|[-+]?\s*$", next_line)
            if block_match:
                i += 2
                content_lines = []
                while i < len(lines):
                    content_line = lines[i]
                    content_indent = len(content_line) - len(content_line.lstrip())
                    # End of literal: same or less indent and looks like next key
                    if content_indent <= indent and content_line.strip():
                        if content_line.strip().endswith(":") or (
                            content_line.strip().startswith("-")
                            and ":" in content_line
                        ):
                            break
                    content_lines.append(content_line)
                    i += 1
                # Escape for YAML double-quoted: \ -> \\, " -> \", newline -> \n
                raw = "\n".join(content_lines)
                escaped = raw.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                result.append(f'{indent_str}code: "{escaped}"')
                continue
        result.append(line)
        i += 1
    return "\n".join(result)

class Agent:
    def __init__(self, llm, msgs=None):
        self._llm = llm
        if not msgs:
            self._msgs = []
        else:
            self._msgs = msgs
        # Token usage tracking
        self.total_tokens_used = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0

    def set_llm(self, llm):
        self._llm = llm

    def _parse_yaml_response(self, response: str):
        parse_result = extract_code_block(response, keyword="yaml")
        # 清理空字符和其他不可打印的控制字符（保留换行符、制表符等）
        parse_result = ''.join(char for char in parse_result if char.isprintable() or char in '\n\r\t')
        # Convert literal code blocks (code: |) to quoted strings so C/code colons don't break YAML
        parse_result = _normalize_yaml_literal_code_blocks(parse_result)
        parse_result = yaml.safe_load(parse_result)
        return parse_result

    def _parse_json_response(self, response: str):
        """Parse JSON from ```json ... ``` block. Code with # or : in values won't break parsing."""
        parse_result = extract_code_block(response, keyword="json")
        parse_result = ''.join(char for char in parse_result if char.isprintable() or char in '\n\r\t')
        return json.loads(parse_result)

    def _parse_response(
        self, response: str, load_json: bool = False, schema: BaseModel = None
    ):
        parse_result = extract_code_block(response, keyword="yaml")

        if not load_json:
            return parse_result

        for i in range(2):
            try:
                print(f"parse_result: {parse_result}")
                parse_result = json.loads(parse_result)
                break
            except Exception as e:
                if i == 1:
                    raise e
                parse_result = replace_json_string(parse_result)

        if not schema:
            return parse_result

        if isinstance(parse_result, list):
            output = [schema.model_validate(item) for item in parse_result]
        else:
            output = schema.model_validate(parse_result)

        return output

    def _split_response(self, response):
        if hasattr(response, "reasoning_content") and response.reasoning_content:
            return response.content, response.reasoning_content

        res = response.content.split("</think>")
        if len(res) == 1:
            return res[0], ""

        return res[-1], "</think>".join(res[0:-1])

    def _invoke(self, input, retry=3):
        for i in range(retry):
            try:
                # Use get_openai_callback to track token usage
                try:
                    with get_openai_callback() as cb:
                        response = self._llm.invoke([HumanMessage(content=input)])
                        # Update token statistics
                        self.total_tokens_used += cb.total_tokens
                        self.total_prompt_tokens += cb.prompt_tokens
                        self.total_completion_tokens += cb.completion_tokens
                        self.total_cost += cb.total_cost
                    return response
                except Exception as cb_error:
                    # If callback fails, still invoke LLM but log warning
                    logger.warning(f"Failed to track token usage: {str(cb_error)}")
                    return self._llm.invoke([HumanMessage(content=input)])
            except Exception as e:
                if i == retry - 1:
                    raise e
                logger.warning(
                    f"LLM invocation failed, retrying (attempt {i+1}): {str(e)}"
                )

    def invoke_with_code_block(self, input):
        content = self.invoke(input)
        return extract_code_block(content, keyword="")

    def invoke(self, input): # no history by default
        # if no_history:
        #     self._msgs = []
        self._msgs = []
        logger.info(f"Agent received input: {input}\n")
        # self._msgs.append(HumanMessage(content=input))

        content, reasoning_content = self._split_response(self._invoke(input))
        if reasoning_content:
            logger.info(f"Agent produced reasoning content: {reasoning_content}\n")

        logger.info(f"Agent produced output: {content}\n")
        # self._msgs.append(AIMessage(content=content))

        return content

    def invoke_with_structured_output(
        self,
        input,
        load_json: bool = True,
        schema: BaseModel = None,
        retry: int = 3,
        feedback: str = "```yaml ```",
    ):
        idx = len(self._msgs) + 1

        for i in range(retry):
            content = self.invoke(input=input)
            try:
                output = self._parse_yaml_response(content)
                break
            except Exception as e:
                if i == retry - 1:
                    raise e
                logger.warning(f"Failed to parse the structured output: {str(e)}")
                input = f"Parse structured response `{content}` failed: {str(e)}. Please output in the following format: {feedback}."
            # try:
                # output = self._parse_response(
                #     response=content, load_json=load_json, schema=schema
                # )
                # break

            # except Exception as e:
            #     if schema:
            #         feedback = f"""```json\n{schema.model_fields}```"""
            #     input = f"Parse structured response `{content}` failed: {str(e)}. Please output in the following schema: {feedback}."
            #     logger.warning(f"Failed to parse the structured output: {str(e)}")
            #     if i == retry - 1:
            #         raise e

        # self._msgs.insert(idx, self._msgs[-1])
        # self.retain_first_k_messages(idx + 1)

        # logger.info(f"Agent produced structured output: {output}\n")
        return output

    def set_system_prompt(self, prompt, verbose=False):
        if self._msgs:
            self._msgs[0] = SystemMessage(content=prompt)
        else:
            self._msgs = [SystemMessage(content=prompt)]

        if verbose:
            logger.info(f"System prompt: {prompt}\n")

    def get_history(self):
        return self._msgs

    def set_history(self, history):
        self._msgs = history

    def clear_history(self):
        self._msgs = []

    def insert_message(self, index, message):
        self._msgs.insert(index, message)

    def append_message(self, message):
        self._msgs.append(message)

    def remove_last_k_messages(self, k):
        self._msgs = self._msgs[:-k]

    def retain_first_k_messages(self, k):
        self._msgs = self._msgs[:k]

    def print_history(self):
        for i, msg in enumerate(self._msgs):
            logger.info(f"Message {i}: {msg.content}\n")
    
    def get_token_stats(self):
        """获取 token 使用统计信息"""
        return {
            "total_tokens": self.total_tokens_used,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_cost": self.total_cost
        }
    
    def reset_token_stats(self):
        """重置 token 统计信息"""
        self.total_tokens_used = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0


class OneRoundAgent:
    """
    One-round agent for simple prompt-based interaction.
    Support structured/unstructured output schema.
    The output format is string (json) by default, but can be customized by postprocess_func.
    """

    def __init__(
        self,
        llm,
        prompt: str,
        output_schema: BaseModel = None,
        template_format="f-string",
        postprocess_func: callable = None,
    ):
        self.llm = llm
        self.prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    prompt, template_format=template_format
                ),
            ]
        )
        self.output_schema = output_schema
        if output_schema:
            self.agent = create_structured_output_runnable(
                output_schema=output_schema,
                llm=self.llm,
                prompt=self.prompt,
            )
        else:
            self.agent = self.prompt | self.llm
        self.postprocess_func = postprocess_func

    def invoke(self, input_dict):
        logger.info(f"LLM received input: {self.prompt.format(**input_dict)}\n")
        res = self.agent.invoke(input_dict)
        if not self.output_schema:
            res = res.content
        else:
            res = res.json()
        if self.postprocess_func:
            res = self.postprocess_func(res)
        logger.info(f"LLM produced output: {res}\n")
        return res

if __name__ == "__main__":
    response = textwrap.dedent("""
    ```yaml
    tool_name: write_file
    tool_args:
        start_line: 144
        end_line: 146
    ```
    """).strip()
    def parse_yaml_response(response: str):
        parse_result = extract_code_block(response, keyword="yaml")
        parse_result = yaml.safe_load(parse_result)
        return parse_result
    parse_result = parse_yaml_response(response)
    print(parse_result)