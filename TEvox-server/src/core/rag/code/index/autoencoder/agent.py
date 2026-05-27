from src.utils import logger, Agent
from pydantic import BaseModel, Field
from .prompts import (
    generate_document_from_code_prompt,
    generate_code_from_document_prompt,
    regenerate_document_from_code_prompt,
    decide_regenerate_or_stop_from_code_prompt,
    generate_document_from_file_prompt,
    generate_file_from_document_prompt,
    regenerate_document_from_file_prompt,
    decide_regenerate_or_stop_from_file_prompt,
    generate_document_from_directory_tree_prompt,
    generate_directory_tree_from_document_prompt,
    regenerate_document_from_directory_tree_prompt,
    decide_regenerate_or_stop_from_directory_tree_prompt,
    generate_document_from_global_variable_prompt,
    generate_global_variable_from_document_prompt,
    decide_global_variable_regeneration_or_stop_prompt,
    regenerate_document_from_global_variable_prompt
)

class regenerate_or_stop(BaseModel):
    action: str = Field(description="regenerate or stop")
    reason: str = Field(description="Explain why you decide to regenerate or stop")

class what_how_document(BaseModel):
    what: str = Field(description="Functional description - what the code does")
    how: str = Field(description="Implementation details - how the code works")

class AutoEncoderAgent:
    def __init__(self, agent: Agent):
        self.agent = agent
    
    def generate_document_from_code(self, target_code, context=""):
        """从代码中提取文档，支持context信息，返回What/How结构化文档"""
        prompt = generate_document_from_code_prompt.format(
            target_code=target_code, 
            context=context
        )
        output = self.agent.invoke_with_structured_output(
            prompt,
            schema=what_how_document
        )
        self.agent.clear_history()
        logger.info(f"Extract document: what={output.what[:100]}..., how={output.how[:100]}...")
        return output

    def generate_code_from_document(self, what_how_doc):
        """基于What/How文档生成代码"""
        if isinstance(what_how_doc, what_how_document):
            what_description = what_how_doc.what
            how_description = what_how_doc.how
        else:
            # 向后兼容：如果传入字符串，尝试作为what描述
            what_description = str(what_how_doc)
            how_description = "Implementation details not specified"
            
        prompt = generate_code_from_document_prompt.format(
            what_description=what_description,
            how_description=how_description
        )
        output = self.agent.invoke(prompt)
        self.agent.clear_history()
        logger.info(f"Generate code based on document: {output}")
        return output
    
    def decide_regenerate_or_stop_from_code(self, target_code, what_how_doc, regenerated_code):
        """决定是否需要重新生成文档（基于What/How文档）"""
        if isinstance(what_how_doc, what_how_document):
            current_what = what_how_doc.what
            current_how = what_how_doc.how
        else:
            # 向后兼容
            current_what = str(what_how_doc)
            current_how = "Implementation details not specified"
            
        prompt = decide_regenerate_or_stop_from_code_prompt.format(
            target_code=target_code,
            current_what=current_what,
            current_how=current_how,
            regenerated_code=regenerated_code
        )
        logger.info(f"Determine regeneration or stop: {prompt}")
        
        res = self.agent.invoke_with_structured_output(
            prompt,
            schema = regenerate_or_stop
        )
        self.agent.clear_history()
        logger.info(f"Determine regeneration or stop: {res}")
        if res.action == "regenerate":
            return True
        else:
            return False
        
    def regenerate_document_from_code(self, target_code, what_how_doc, regenerated_code):
        """重新生成文档（基于What/How文档）"""
        if isinstance(what_how_doc, what_how_document):
            current_what = what_how_doc.what
            current_how = what_how_doc.how
        else:
            # 向后兼容
            current_what = str(what_how_doc)
            current_how = "Implementation details not specified"
            
        prompt = regenerate_document_from_code_prompt.format(
            target_code=target_code,
            current_what=current_what,
            current_how=current_how,
            regenerated_code=regenerated_code
        )
        output = self.agent.invoke_with_structured_output(
            prompt,
            schema=what_how_document
        )
        self.agent.clear_history()
        logger.info(f"Regenerate document: what={output.what[:100]}..., how={output.how[:100]}...")
        return output
    

    
    def generate_document_from_file(self, structured_info):
        """基于结构化信息生成文档描述，返回包含What和How的结构化输出"""
        prompt = generate_document_from_file_prompt.format(
            structured_info=structured_info
        )
        output = self.agent.invoke_with_structured_output(
            prompt,
            schema=what_how_document
        )
        self.agent.clear_history()
        logger.info(f"Generate document from file: what={output.what[:100]}..., how={output.how[:100]}...")
        return output
    
    def generate_file_from_document(self, what_how_doc):
        """基于文档描述重新生成结构化信息，接受包含What和How的文档对象"""
        if isinstance(what_how_doc, what_how_document):
            what_description = what_how_doc.what
            how_description = what_how_doc.how
        else:
            # 向后兼容：如果传入的是字符串，尝试解析或使用原有逻辑
            what_description = str(what_how_doc)
            how_description = "Implementation details not specified"
            
        prompt = generate_file_from_document_prompt.format(
            what_description=what_description,
            how_description=how_description
        )
        output = self.agent.invoke(prompt)
        self.agent.clear_history()
        logger.info(f"Generate file from document: {output}")
        return output
    
    def decide_regenerate_or_stop_from_file(self, original_structured_info, regenerated_structured_info):
        """决定是否需要重新生成文档（基于结构化信息比较）
        
        Returns:
            tuple: (need_regenerate: bool, reason: str)
        """
        prompt = decide_regenerate_or_stop_from_file_prompt.format(
            original_structured_info=original_structured_info,
            regenerated_structured_info=regenerated_structured_info
        )
        logger.info(f"Determine file regeneration or stop: {prompt}")
        
        res = self.agent.invoke_with_structured_output(
            prompt,
            schema=regenerate_or_stop
        )
        self.agent.clear_history()
        logger.info(f"Determine file regeneration or stop: {res}")
        
        need_regenerate = res.action == "regenerate"
        return need_regenerate, res.reason
    
    def regenerate_document_from_file(self, original_structured_info, current_what_how_doc, regenerated_structured_info):
        """基于结构化信息差异重新生成文档，返回改进的What和How"""
        if isinstance(current_what_how_doc, what_how_document):
            current_what = current_what_how_doc.what
            current_how = current_what_how_doc.how
        else:
            # 向后兼容
            current_what = str(current_what_how_doc)
            current_how = "Implementation details not specified"
            
        prompt = regenerate_document_from_file_prompt.format(
            original_structured_info=original_structured_info,
            current_what=current_what,
            current_how=current_how,
            regenerated_structured_info=regenerated_structured_info
        )
        output = self.agent.invoke_with_structured_output(
            prompt,
            schema=what_how_document
        )
        self.agent.clear_history()
        logger.info(f"Regenerate document from file: what={output.what[:100]}..., how={output.how[:100]}...")
        return output
    

    

    

    
    def generate_document_from_directory_tree(self, directory_tree_info):
        """基于目录树分析生成项目文档"""
        prompt = generate_document_from_directory_tree_prompt.format(
            directory_tree_info=directory_tree_info
        )
        output = self.agent.invoke_with_structured_output(
            prompt,
            schema=what_how_document
        )
        self.agent.clear_history()
        logger.info(f"Generate document from directory tree: what={output.what[:100]}..., how={output.how[:100]}...")
        return output
    
    def generate_directory_tree_from_document(self, document):
        """基于项目文档重新生成目录树分析"""
        # 如果document是what_how_document对象，提取what和how
        if hasattr(document, 'what') and hasattr(document, 'how'):
            what_description = document.what
            how_description = document.how
        else:
            # 如果是字符串，尝试解析或使用原有逻辑
            what_description = str(document)
            how_description = "Implementation details not specified"
            
        prompt = generate_directory_tree_from_document_prompt.format(
            what_description=what_description,
            how_description=how_description
        )
        output = self.agent.invoke(prompt)
        self.agent.clear_history()
        logger.info(f"Generate directory tree from document: {output}")
        return output
    
    def decide_regenerate_or_stop_from_directory_tree(self, original_directory_tree_info, regenerated_directory_tree_info):
        """决定是否需要重新生成项目文档（基于目录树分析比较）"""
        prompt = decide_regenerate_or_stop_from_directory_tree_prompt.format(
            original_directory_tree_info=original_directory_tree_info,
            regenerated_directory_tree_info=regenerated_directory_tree_info
        )
        logger.info(f"Determine directory tree regeneration or stop: {prompt}")
        
        res = self.agent.invoke_with_structured_output(
            prompt,
            schema=regenerate_or_stop
        )
        self.agent.clear_history()
        logger.info(f"Determine directory tree regeneration or stop: {res}")
        if res.action == "regenerate":
            return True
        else:
            return False
    
    def regenerate_document_from_directory_tree(self, original_directory_tree_info, current_document, regenerated_directory_tree_info):
        """基于目录树分析差异重新生成项目文档"""
        # 如果current_document是what_how_document对象，提取what和how
        if hasattr(current_document, 'what') and hasattr(current_document, 'how'):
            current_what = current_document.what
            current_how = current_document.how
        else:
            # 如果是字符串，尝试解析或使用原有逻辑
            current_what = str(current_document)
            current_how = "Implementation details not specified"
            
        prompt = regenerate_document_from_directory_tree_prompt.format(
            original_directory_tree_info=original_directory_tree_info,
            current_what=current_what,
            current_how=current_how,
            regenerated_directory_tree_info=regenerated_directory_tree_info
        )
        output = self.agent.invoke_with_structured_output(
            prompt,
            schema=what_how_document
        )
        self.agent.clear_history()
        logger.info(f"Regenerate document from directory tree: what={output.what[:100]}..., how={output.how[:100]}...")
        return output
    
    def generate_document_from_global_variable(self, variable_info):
        """基于全局变量信息生成文档描述，返回包含What和How的结构化输出"""
        prompt = generate_document_from_global_variable_prompt.format(
            variable_name=variable_info.get('name', ''),
            file_path=variable_info.get('file_path', ''),
            definition=variable_info.get('metadata', {}).get('definition', ''),
            references_count=len(variable_info.get('metadata', {}).get('references', [])),
            referencing_files_count=len(variable_info.get('metadata', {}).get('referencing_files', []))
        )
        output = self.agent.invoke_with_structured_output(
            prompt,
            schema=what_how_document
        )
        self.agent.clear_history()
        logger.info(f"Generate document from global variable: what={output.what[:100]}..., how={output.how[:100]}...")
        return output
    
    def generate_global_variable_from_document(self, what_how_doc):
        """基于文档描述重新生成全局变量信息，接受包含What和How的文档对象"""
        if isinstance(what_how_doc, what_how_document):
            what_description = what_how_doc.what
            how_description = what_how_doc.how
        else:
            # 向后兼容：如果传入的是字符串，尝试解析或使用原有逻辑
            what_description = str(what_how_doc)
            how_description = "Implementation details not specified"
            
        prompt = generate_global_variable_from_document_prompt.format(
            what_description=what_description,
            how_description=how_description
        )
        output = self.agent.invoke(prompt)
        self.agent.clear_history()
        logger.info(f"Generate global variable from document: {output}")
        return output
    
    def decide_regenerate_or_stop_from_global_variable(self, original_variable_info, regenerated_variable_info):
        """决定是否需要重新生成全局变量文档（基于原始和重新生成的信息比较）
        
        Returns:
            tuple: (need_regenerate: bool, reason: str)
        """
        prompt = decide_global_variable_regeneration_or_stop_prompt.format(
            original_variable_name=original_variable_info.get('name', ''),
            original_file_path=original_variable_info.get('file_path', ''),
            original_definition=original_variable_info.get('metadata', {}).get('definition', ''),
            regenerated_variable_info=regenerated_variable_info
        )
        logger.info(f"Determine global variable regeneration or stop: {prompt}")
        
        res = self.agent.invoke_with_structured_output(
            prompt,
            schema=regenerate_or_stop
        )
        self.agent.clear_history()
        logger.info(f"Determine global variable regeneration or stop: {res}")
        
        need_regenerate = res.action == "regenerate"
        return need_regenerate, res.reason
    
    def regenerate_document_from_global_variable(self, original_variable_info, current_what_how_doc, regenerated_variable_info):
        """基于全局变量信息差异重新生成文档，返回改进的What和How"""
        if isinstance(current_what_how_doc, what_how_document):
            current_what = current_what_how_doc.what
            current_how = current_what_how_doc.how
        else:
            # 向后兼容
            current_what = str(current_what_how_doc)
            current_how = "Implementation details not specified"
            
        prompt = regenerate_document_from_global_variable_prompt.format(
            original_variable_name=original_variable_info.get('name', ''),
            original_file_path=original_variable_info.get('file_path', ''),
            original_definition=original_variable_info.get('metadata', {}).get('definition', ''),
            current_what=current_what,
            current_how=current_how,
            regenerated_variable_info=regenerated_variable_info
        )
        output = self.agent.invoke_with_structured_output(
            prompt,
            schema=what_how_document
        )
        self.agent.clear_history()
        logger.info(f"Regenerate document from global variable: what={output.what[:100]}..., how={output.how[:100]}...")
        return output
