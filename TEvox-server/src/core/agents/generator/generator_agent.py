import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from src.core.rag.doc.query.nx_query_engine import NxQueryEngine
from src.utils import get_llm, Agent
from src.base import DefaultConfig

# 核心数据模型
class WorkflowStep(BaseModel):
    """工作流步骤"""
    current_environment_state: str = Field(description="当前环境状态描述")
    reasoning_process: str = Field(description="决策推理过程")
    action: str = Field(description="可执行动作")

class Workflow(BaseModel):
    """工作流"""
    workflow_id: str = Field(description="工作流唯一标识")
    description: str = Field(description="工作流文本描述")
    trajectory: List[WorkflowStep] = Field(description="包含的步骤列表")

class Experience(BaseModel):
    """经验"""
    experience_id: str = Field(description="经验唯一标识")
    task_description: str = Field(description="任务描述")
    behavior_trajectory: List[WorkflowStep] = Field(description="行为的轨迹")
    result: str = Field(description="执行结果")
    evaluation: Dict[str, Any] = Field(description="评价信息")

class QueryDecomposition(BaseModel):
    queries: List[str] = Field(description="分解后的检索查询列表")

class CodeImplementation(BaseModel):
    code: str = Field(description="生成的代码")
    explanation: str = Field(description="代码说明")

class ValidationResult(BaseModel):
    is_functionally_correct: bool = Field(description="生成的代码是否功能性正确")
    differences: List[str] = Field(description="与源代码有差异的地方")
    difference_analysis: str = Field(description="对有差异的地方进行分析")

class ActionAgent:
    """动作执行代理"""
    
    def __init__(self, llm: Agent):
        self.llm = llm
    
    def execute_step(self, step: WorkflowStep, step_number: int, context: str = "") -> str:
        """执行单个步骤，返回执行结果文本"""
        
        prompt = f"""请执行以下工作流步骤：

步骤 {step_number}:
- 环境状态: {step.current_environment_state}
- 推理过程: {step.reasoning_process}
- 动作: {step.action}

上下文信息: {context}

请按照步骤要求执行动作，并返回执行结果的详细描述。"""

        try:
            response = self.llm.invoke(prompt)
            return response
        except Exception as e:
            return f"执行步骤 {step_number} 时出错: {str(e)}"

class WorkflowMemory:
    """工作流记忆库"""
    def __init__(self, storage_path: str = "evox-server/.rag/xiaozhi/prompt_storage"):
        self.storage_path = storage_path
        self.workflows: Dict[str, Workflow] = {}
        self.experiences: Dict[str, Experience] = {}
        self._load_data()
    
    def get_workflows(self) -> List[Workflow]:
        """获取所有工作流"""
        return list(self.workflows.values())
    
    def add_workflow(self, workflow: Workflow):
        """添加新工作流"""
        self.workflows[workflow.workflow_id] = workflow
        self._save_data()
    
    def add_experience(self, experience: Experience):
        """添加新经验"""
        self.experiences[experience.experience_id] = experience
        self._save_data()
    
    def _load_data(self):
        """加载数据"""
        try:
            if os.path.exists(f"{self.storage_path}/workflows.json"):
                with open(f"{self.storage_path}/workflows.json", 'r', encoding='utf-8') as f:
                    workflows_data = json.load(f)
                    for wf_data in workflows_data.values():
                        workflow = Workflow(**wf_data)
                        self.workflows[workflow.workflow_id] = workflow
            
            if os.path.exists(f"{self.storage_path}/experiences.json"):
                with open(f"{self.storage_path}/experiences.json", 'r', encoding='utf-8') as f:
                    exp_data = json.load(f)
                    for exp in exp_data.values():
                        experience = Experience(**exp)
                        self.experiences[experience.experience_id] = experience
        except Exception as e:
            print(f"Warning: Failed to load workflow memory: {e}")
    
    def _save_data(self):
        """保存数据"""
        os.makedirs(self.storage_path, exist_ok=True)
        
        try:
            with open(f"{self.storage_path}/workflows.json", 'w', encoding='utf-8') as f:
                workflows_dict = {wid: wf.model_dump() for wid, wf in self.workflows.items()}
                json.dump(workflows_dict, f, ensure_ascii=False, indent=2)
            
            with open(f"{self.storage_path}/experiences.json", 'w', encoding='utf-8') as f:
                exp_dict = {eid: exp.model_dump() for eid, exp in self.experiences.items()}
                json.dump(exp_dict, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save workflow memory: {e}")

class GeneratorAgent:
    def __init__(self, config_path: str = None):
        """
        初始化代码生成代理
        
        Args:
            config_path: prompt配置文件路径，默认为当前目录下的prompt.json
        """
        # 设置默认配置文件路径
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "prompt.json")
        
        # 初始化NxQueryEngine
        self.query_engine = NxQueryEngine({"root_path": ".rag"})
        
        # 初始化LLM和Agent
        self.llm = get_llm(model_name=DefaultConfig.agent_model)
        self.agent = Agent(self.llm)
        
        # 加载prompt配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.prompts = json.load(f)
        
        # 加载query_result.json
        query_result_path = os.path.join(os.path.dirname(__file__), "query_result.json")
        with open(query_result_path, 'r', encoding='utf-8') as f:
            self.query_results = json.load(f)
        
        # 新增工作流记忆和动作代理
        self.workflow_memory = WorkflowMemory()
        self.action_agent = ActionAgent(self.agent)
    
    def _analyze_requirement(self, requirement: str) -> str:
        """
        分析用户需求，将其解析为具体的实现步骤和技术要点
        
        Args:
            requirement: 用户需求
            
        Returns:
            需求分析结果（纯文本）
        """
        prompt = self.prompts["retrieval_prompt"]["requirement_analysis"]
        prompt = prompt.format(requirement=requirement)
        
        response = self.agent.invoke(prompt)
        return response
    
    def _decompose_queries(self, requirement_analysis: str) -> List[str]:
        """
        基于需求分析结果，将需求分解为多个检索查询
        
        Args:
            requirement_analysis: 需求分析结果
            
        Returns:
            分解后的查询列表
        """
        prompt = self.prompts["retrieval_prompt"]["query_decomposition"]
        prompt = prompt.format(requirement_analysis=requirement_analysis)
        
        response = self.agent.invoke_with_structured_output(
            prompt, 
            QueryDecomposition
        )
        
        return response["queries"]
    
    def _save_query_results(self, query_results: Dict[str, Any], filename: str = None):
        """
        将查询结果保存到JSON文件
        
        Args:
            query_results: 查询结果字典
            filename: 文件名，如果为None则自动生成
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"query_results_{timestamp}.json"
        
        filepath = os.path.join(os.path.dirname(__file__), filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(query_results, f, ensure_ascii=False, indent=2)
        
        print(f"查询结果已保存到: {filepath}")
    
    def retrieve_context(self, user_requirement: str) -> Dict[str, Any]:
        """
        基于用户需求检索相关文档片段
        
        Args:
            user_requirement: 用户需求
            
        Returns:
            包含检索结果的字典
        """
        # 1. 需求分析
        requirement_analysis = self._analyze_requirement(user_requirement)
        
        # 2. 查询分解
        decomposed_queries = self._decompose_queries(requirement_analysis)
        
        # 3. 多轮检索
        all_results = []
        query_results = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "user_requirement": user_requirement,
                "requirement_analysis": requirement_analysis,
                "total_queries": len(decomposed_queries)
            },
            "queries": {}
        }
        
        for i, query in enumerate(decomposed_queries):
            results = []
            
            for textunit in self.query_engine.query(query, entry_limit=10, top_k=50):
                results.append(textunit.llm_content)
            
            query_results["queries"][f"query_{i}"] = {
                "query": query,
                "results_count": len(results),
                "results": results
            }
            all_results.extend(results)
        
        # 4. 去重
        unique_results = list(set(all_results))
        
        query_results["metadata"]["total_results"] = len(all_results)
        query_results["metadata"]["unique_results"] = len(unique_results)
        
        # 5. 保存查询结果到JSON文件
        self._save_query_results(query_results)
        
        return {
            "requirement_analysis": requirement_analysis,
            "decomposed_queries": decomposed_queries,
            "query_results": query_results,
            "retrieved_context": unique_results
        }
    
    def generate_code(self, requirement: str, context: List[str]) -> Dict[str, str]:
        """
        基于用户原始需求和检索上下文生成代码
        
        Args:
            requirement: 用户原始需求
            context: 检索到的文档片段列表
            
        Returns:
            包含代码和说明的字典
        """
        # 获取代码示例
        code_example = self.prompts["generation_prompt"]["code_example"]
        
        # 获取代码实现prompt
        code_implementation_prompt = self.prompts["generation_prompt"]["code_implementation"]
        
        # 组合完整的prompt
        context_text = "\n\n".join(context)
        full_prompt = f"{code_example}\n\n{code_implementation_prompt}"
        
        # 使用字符串替换，避免与代码示例中的花括号冲突
        full_prompt = full_prompt.replace("{requirement}", requirement)
        full_prompt = full_prompt.replace("{context}", context_text)
        
        response = self.agent.invoke_with_structured_output(
            full_prompt,
            CodeImplementation
        )
        
        return {
            "code": response["code"],
            "explanation": response["explanation"]
        }
    
    def process(self, user_requirement: str) -> Dict[str, Any]:
        """
        处理用户需求，返回检索结果和生成的代码
        
        Args:
            user_requirement: 用户需求
            
        Returns:
            包含检索结果和生成代码的字典
        """
        # 1. 检索相关文档
        retrieval_result = self.retrieve_context(user_requirement)
        
        # 2. 生成代码 - 直接使用原始需求
        code_result = self.generate_code(
            user_requirement,  # 改为直接传递原始需求
            retrieval_result["retrieved_context"]
        )
        
        return {
            "requirement": user_requirement,
            "requirement_analysis": retrieval_result["requirement_analysis"],
            "decomposed_queries": retrieval_result["decomposed_queries"],
            "query_results": retrieval_result["query_results"],
            "retrieved_context": retrieval_result["retrieved_context"],
            "generated_code": code_result["code"],
            "explanation": code_result["explanation"]
        }
    
    def get_query_requirement(self, index: int = 0) -> str:
        """
        从query_result.json中获取指定索引的requirement
        
        Args:
            index: 查询结果的索引，默认为0
            
        Returns:
            对应的requirement字符串
        """
        if index >= len(self.query_results["query_result"]):
            raise IndexError(f"索引 {index} 超出范围，共有 {len(self.query_results['query_result'])} 个查询结果")
        
        return self.query_results["query_result"][index]["query"]["requirement"]
    
    def get_expected_code(self, index: int = 0) -> str:
        """
        从query_result.json中获取指定索引的预期代码
        
        Args:
            index: 查询结果的索引，默认为0
            
        Returns:
            对应的预期代码字符串
        """
        if index >= len(self.query_results["query_result"]):
            raise IndexError(f"索引 {index} 超出范围，共有 {len(self.query_results['query_result'])} 个查询结果")
        
        return self.query_results["query_result"][index]["result"]["code"]
    
    def validation_result(self, generated_code: str, expected_code: str, requirement: str) -> Dict[str, Any]:
        """
        验证生成的代码与预期代码的差异
        
        Args:
            generated_code: 生成的代码
            expected_code: 预期的代码
            requirement: 用户需求
            
        Returns:
            验证结果字典
        """
        prompt = self.prompts["validation_prompt"]["code_validation"]
        prompt = prompt.format(
            requirement=requirement,
            generated_code=generated_code,
            expected_code=expected_code
        )
        
        response = self.agent.invoke_with_structured_output(
            prompt,
            ValidationResult
        )
        
        return {
            "is_functionally_correct": response["is_functionally_correct"],
            "differences": response["differences"],
            "difference_analysis": response["difference_analysis"]
        }
    
    def generate_and_execute_workflow(self, requirement: str) -> Dict[str, Any]:
        """生成工作流并执行"""
        
        # 1. 生成或获取工作流
        workflow = self._get_or_generate_workflow(requirement)
        
        # 2. 执行工作流的每一步
        execution_results = []
        context = f"任务需求: {requirement}"
        
        for i, step in enumerate(workflow.trajectory):
            # 执行步骤
            step_result = self.action_agent.execute_step(step, i + 1, context)
            execution_results.append(step_result)
            
            # 更新上下文
            context += f"\n步骤 {i+1} 结果: {step_result}"
        
        # 3. 总结为experience并保存
        experience = self._create_experience_from_execution(requirement, workflow, execution_results)
        self.workflow_memory.add_experience(experience)
        
        return {
            "workflow": workflow.model_dump(),
            "execution_results": execution_results,
            "experience": experience.model_dump()
        }
    
    def _get_or_generate_workflow(self, requirement: str) -> Workflow:
        """获取现有工作流或生成新的工作流"""
        
        # 1. 尝试从记忆库获取相关工作流
        existing_workflows = self.workflow_memory.get_workflows()
        if existing_workflows:
            # 简单选择第一个工作流（可以后续优化为智能选择）
            return existing_workflows[0]
        
        # 2. 如果没有现有工作流，生成新的
        return self._generate_new_workflow(requirement)
    
    def _generate_new_workflow(self, requirement: str) -> Workflow:
        """生成新的工作流"""
        
        prompt = f"""请为以下任务生成一个工作流：

任务需求: {requirement}

请生成一个包含3-5个步骤的工作流，每个步骤应该：
1. 有明确的环境状态描述
2. 包含清晰的推理过程
3. 指定具体的执行动作

请以JSON格式输出：

```json
{{
    "description": "工作流的描述",
    "trajectory": [
        {{
            "current_environment_state": "当前环境状态描述",
            "reasoning_process": "决策推理过程",
            "action": "可执行动作"
        }}
    ]
}}
```"""

        try:
            response = self.agent.invoke_with_structured_output(
                prompt,
                Dict[str, Any]
            )
            
            # 生成唯一ID
            workflow_id = f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            response["workflow_id"] = workflow_id
            
            workflow = Workflow(**response)
            
            # 保存到记忆库
            self.workflow_memory.add_workflow(workflow)
            
            return workflow
        except Exception as e:
            print(f"Warning: Failed to generate workflow: {e}")
            # 返回默认工作流
            return self._create_default_workflow(requirement)
    
    def _create_default_workflow(self, requirement: str) -> Workflow:
        """创建默认工作流"""
        return Workflow(
            workflow_id=f"default_wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            description=f"默认工作流: {requirement}",
            trajectory=[
                WorkflowStep(
                    current_environment_state="开始任务",
                    reasoning_process="分析任务需求",
                    action="analyze_requirement"
                ),
                WorkflowStep(
                    current_environment_state="任务分析完成",
                    reasoning_process="执行任务",
                    action="execute_task"
                ),
                WorkflowStep(
                    current_environment_state="任务执行完成",
                    reasoning_process="验证结果",
                    action="verify_result"
                )
            ]
        )
    
    def _create_experience_from_execution(self, requirement: str, workflow: Workflow, execution_results: List[str]) -> Experience:
        """从执行结果创建经验"""
        
        # 将执行结果转换为工作流步骤（简化处理）
        behavior_trajectory = [
            WorkflowStep(
                current_environment_state="执行工作流",
                reasoning_process="按照工作流步骤执行任务",
                action="execute_workflow"
            )
        ]
        
        # 总结执行结果
        final_result = "执行完成"
        if execution_results:
            final_result = execution_results[-1]
        
        experience_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return Experience(
            experience_id=experience_id,
            task_description=requirement,
            behavior_trajectory=behavior_trajectory,
            result=final_result,
            evaluation={
                "workflow_id": workflow.workflow_id,
                "steps_executed": len(execution_results)
            }
        )

def main():
    agent = GeneratorAgent()
    
    # 从query_result.json中获取requirement
    requirement = agent.get_query_requirement(0)
    
    print("任务需求:")
    print(requirement)
    print("\n" + "="*50 + "\n")
    
    # 生成工作流并执行
    result = agent.generate_and_execute_workflow(requirement)
    
    print("工作流执行结果:")
    print(f"工作流ID: {result['workflow']['workflow_id']}")
    print(f"工作流描述: {result['workflow']['description']}")
    print(f"执行步骤数: {len(result['execution_results'])}")
    
    print("\n执行详情:")
    for i, step_result in enumerate(result['execution_results']):
        print(f"\n步骤 {i+1}:")
        print(f"  执行结果: {step_result}")
    
    print("\n" + "="*50 + "\n")
    print("经验记录:")
    print(f"经验ID: {result['experience']['experience_id']}")
    print(f"任务描述: {result['experience']['task_description']}")
    print(f"行为轨迹: {len(result['experience']['behavior_trajectory'])} 个步骤")
    print(f"最终结果: {result['experience']['result']}")
    
    # 显示工作流记忆状态
    print("\n" + "="*50 + "\n")
    print("工作流记忆状态:")
    print(f"存储的工作流数量: {len(agent.workflow_memory.workflows)}")
    print(f"存储的经验数量: {len(agent.workflow_memory.experiences)}")
    
    # 测试原有的代码生成功能
    print("\n" + "="*50 + "\n")
    print("测试原有代码生成功能:")
    original_result = agent.process(requirement)
    
    print("生成的代码:")
    print(original_result["generated_code"])
    print("\n代码说明:")
    print(original_result["explanation"])
    
    # 获取预期代码并验证
    expected_code = agent.get_expected_code(0)
    validation = agent.validation_result(
        original_result["generated_code"], 
        expected_code, 
        requirement
    )
    
    print("\n验证结果:")
    print(f"功能正确性: {validation['is_functionally_correct']}")
    print(f"差异列表: {validation['differences']}")
    print(f"差异分析: {validation['difference_analysis']}")

def test_generate_code():
    agent = GeneratorAgent()
    requirement = agent.get_query_requirement(0)
    result = agent.generate_code(requirement, [])
    print(result["code"])
    print(result["explanation"])

# 使用示例
if __name__ == "__main__":
    main()
    #test_generate_code()
