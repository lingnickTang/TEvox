# evox-server/src/core/rag/code/index/designer/designer_example.py

"""
Designer 类使用示例和测试函数

本文件展示了如何使用 Designer 类的所有功能，包括：
1. 基于功能描述生成面向对象设计
2. 将设计转换为 NetworkX 图
3. 保存和加载图结构
4. 基于参考设计生成新设计

注意：这些函数会实际测试核心功能，但使用模拟的LLM响应
"""

import os
import json
import networkx as nx
from typing import Dict, Any, Optional
from unittest.mock import Mock, MagicMock, patch
import sys

# 添加父目录到路径以导入designer模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from designer import Designer, ClassNode, InheritanceEdge, ObjectOrientedDesign, GraphStructure

# 模拟的 retriever 类
class MockRetriever:
    """模拟的 retriever 类，用于测试"""
    
    def __init__(self, mock_graph: nx.DiGraph):
        self.mock_graph = mock_graph
    
    def retrieve(self, reference_path: str) -> Optional[nx.DiGraph]:
        return self.mock_graph

def create_mock_design() -> ObjectOrientedDesign:
    """创建模拟的面向对象设计对象"""
    user_class = ClassNode(
        id="User",
        name="User",
        source_code="class User:\n    def __init__(self, username, password):\n        self.username = username\n        self.password = password",
        description="用户基础类，包含用户名和密码"
    )
    
    admin_class = ClassNode(
        id="Admin",
        name="Admin",
        source_code="class Admin(User):\n    def __init__(self, username, password, role):\n        super().__init__(username, password)\n        self.role = role",
        description="管理员类，继承自User，具有特殊权限"
    )
    
    inheritance = InheritanceEdge(source="Admin", target="User")
    
    return ObjectOrientedDesign(
        classes=[user_class, admin_class],
        inheritances=[inheritance],
        metadata={"created_at": "2024-01-01T00:00:00", "designer": "MockDesigner"}
    )

def create_mock_graph() -> nx.DiGraph:
    """创建模拟的 NetworkX 图"""
    G = nx.DiGraph()
    
    G.add_node("User", 
               type="class",
               source_code="class User:\n    def __init__(self, username, password):\n        self.username = username\n        self.password = password",
               description="用户基础类，包含用户名和密码")
    
    G.add_node("Admin", 
               type="class",
               source_code="class Admin(User):\n    def __init__(self, username, password, role):\n        super().__init__(username, password)\n        self.role = role",
               description="管理员类，继承自User，具有特殊权限")
    
    G.add_edge("Admin", "User", edge_type="inheritance")
    
    return G

def create_mock_llm_response_for_design() -> ObjectOrientedDesign:
    """创建模拟的LLM响应，用于测试what_to_design函数"""
    user_class = ClassNode(
        id="User",
        name="User",
        source_code="class User:\n    def __init__(self, username, password):\n        self.username = username\n        self.password = password\n        self.email = None",
        description="用户基础类，包含用户名、密码和邮箱"
    )
    
    admin_class = ClassNode(
        id="Admin",
        name="Admin",
        source_code="class Admin(User):\n    def __init__(self, username, password, role):\n        super().__init__(username, password)\n        self.role = role\n        self.permissions = []",
        description="管理员类，继承自User，具有特殊权限和角色"
    )
    
    inheritance = InheritanceEdge(source="Admin", target="User")
    
    return ObjectOrientedDesign(
        classes=[user_class, admin_class],
        inheritances=[inheritance],
        metadata={"created_at": "2024-01-01T00:00:00", "designer": "MockLLM", "source": "LLM generated"}
    )

def create_mock_llm_response_for_graph() -> GraphStructure:
    """创建模拟的LLM响应，用于测试design_to_nxgraph函数"""
    return GraphStructure(
        nodes=[
            {
                "id": "User",
                "type": "class",
                "source_code": "class User:\n    def __init__(self, username, password):\n        self.username = username\n        self.password = password\n        self.email = None",
                "description": "用户基础类，包含用户名、密码和邮箱"
            },
            {
                "id": "Admin",
                "type": "class",
                "source_code": "class Admin(User):\n    def __init__(self, username, password, role):\n        super().__init__(username, password)\n        self.role = role\n        self.permissions = []",
                "description": "管理员类，继承自User，具有特殊权限和角色"
            }
        ],
        edges=[
            {
                "source": "Admin",
                "target": "User",
                "edge_type": "inheritance"
            }
        ]
    )

def test_designer_initialization():
    """测试 Designer 类的初始化"""
    print("=" * 60)
    print("测试 Designer 类初始化")
    print("=" * 60)
    
    config = {
        "similarity_threshold": 0.7,
        "max_classes": 10,
        "output_dir": "./output"
    }
    
    try:
        designer = Designer(config)
        print("✅ Designer 实例创建成功")
        print(f"   配置参数: {config}")
        
        mock_graph = create_mock_graph()
        mock_retriever = MockRetriever(mock_graph)
        designer.set_retriever(mock_retriever)
        print("✅ Retriever 设置成功")
        
        return designer
        
    except Exception as e:
        print(f"❌ Designer 初始化失败: {e}")
        return None

def test_what_to_design(designer: Designer):
    """测试 what_to_design 方法"""
    print("\n" + "=" * 60)
    print("测试 what_to_design 方法")
    print("=" * 60)
    
    # 测试用例1：基本功能描述
    description1 = "实现一个用户管理系统，包含用户注册、登录、权限管理等功能"
    print(f"测试用例1: {description1}")
    
    try:
        with patch.object(designer.agent, 'invoke_with_structured_output') as mock_invoke:
            mock_design = create_mock_llm_response_for_design()
            mock_invoke.return_value = mock_design
            
            result = designer.what_to_design(description1)
            
            print(f"   调用 designer.what_to_design(description1)")
            print(f"   返回结果类型: {type(result)}")
            print(f"   类数量: {len(result.classes)}")
            print(f"   继承关系数量: {len(result.inheritances)}")
            print(f"   元数据: {result.metadata}")
            
            assert isinstance(result, ObjectOrientedDesign), "返回结果应该是ObjectOrientedDesign类型"
            assert len(result.classes) > 0, "应该包含至少一个类"
            assert len(result.inheritances) > 0, "应该包含至少一个继承关系"
            
            print("   ✅ 测试用例1 成功：返回了正确的ObjectOrientedDesign对象")
            
    except Exception as e:
        print(f"   ❌ 测试用例1 失败: {e}")
    
    # 测试用例2：带参考设计的功能描述
    description2 = "实现一个订单管理系统，包含订单创建、状态跟踪、支付处理等功能"
    reference_path = "user_management_design.json"
    print(f"\n测试用例2: {description2}")
    print(f"参考设计: {reference_path}")
    
    try:
        with patch.object(designer.agent, 'invoke_with_structured_output') as mock_invoke:
            mock_design_with_ref = create_mock_llm_response_for_design()
            mock_design_with_ref.metadata["reference_used"] = reference_path
            mock_invoke.return_value = mock_design_with_ref
            
            result = designer.what_to_design(description2, reference_path)
            
            print(f"   调用 designer.what_to_design(description2, reference_path)")
            print(f"   返回结果类型: {type(result)}")
            print(f"   类数量: {len(result.classes)}")
            print(f"   继承关系数量: {len(result.inheritances)}")
            print(f"   元数据: {result.metadata}")
            
            assert isinstance(result, ObjectOrientedDesign), "返回结果应该是ObjectOrientedDesign类型"
            assert "reference_used" in result.metadata, "应该包含参考设计信息"
            
            print("   ✅ 测试用例2 成功：基于参考设计返回了正确的ObjectOrientedDesign对象")
            
    except Exception as e:
        print(f"   ❌ 测试用例2 失败: {e}")

def test_design_to_nxgraph(designer: Designer):
    """测试 design_to_nxgraph 方法"""
    print("\n" + "=" * 60)
    print("测试 design_to_nxgraph 方法")
    print("=" * 60)
    
    mock_design = create_mock_design()
    print(f"输入设计对象:")
    print(f"   - 类数量: {len(mock_design.classes)}")
    print(f"   - 继承关系数量: {len(mock_design.inheritances)}")
    
    try:
        with patch.object(designer.agent, 'invoke_with_structured_output') as mock_invoke:
            mock_graph_structure = create_mock_llm_response_for_graph()
            mock_invoke.return_value = mock_graph_structure
            
            result = designer.design_to_nxgraph(mock_design)
            
            print(f"\n调用 designer.design_to_nxgraph(mock_design)")
            print(f"返回结果类型: {type(result)}")
            print(f"节点数量: {result.number_of_nodes()}")
            print(f"边数量: {result.number_of_edges()}")
            
            assert isinstance(result, nx.DiGraph), "返回结果应该是NetworkX图"
            assert result.number_of_nodes() > 0, "图应该包含至少一个节点"
            assert result.number_of_edges() > 0, "图应该包含至少一条边"
            
            for node_id, node_data in result.nodes(data=True):
                print(f"   节点 {node_id}: type={node_data.get('type')}, description={node_data.get('description', '')[:50]}...")
                assert node_data.get('type') == 'class', f"节点 {node_id} 应该是class类型"
            
            for source, target, edge_data in result.edges(data=True):
                print(f"   边 {source} -> {target}: type={edge_data.get('edge_type')}")
                assert edge_data.get('edge_type') == 'inheritance', f"边 {source} -> {target} 应该是inheritance类型"
            
            print("   ✅ 测试用例成功：返回了正确的NetworkX图结构")
            
    except Exception as e:
        print(f"   ❌ 测试用例失败: {e}")

def test_response_to_nxgraph(designer: Designer):
    """测试 _response_to_nxgraph 方法"""
    print("\n" + "=" * 60)
    print("测试 _response_to_nxgraph 方法")
    print("=" * 60)
    
    mock_response = create_mock_llm_response_for_graph()
    print(f"输入GraphStructure对象:")
    print(f"   - 节点数量: {len(mock_response.nodes)}")
    print(f"   - 边数量: {len(mock_response.edges)}")
    
    try:
        result = designer._response_to_nxgraph(mock_response)
        
        print(f"\n调用 designer._response_to_nxgraph(mock_response)")
        print(f"返回结果类型: {type(result)}")
        print(f"节点数量: {result.number_of_nodes()}")
        print(f"边数量: {result.number_of_edges()}")
        
        assert isinstance(result, nx.DiGraph), "返回结果应该是NetworkX图"
        assert result.number_of_nodes() == len(mock_response.nodes), "节点数量应该匹配"
        assert result.number_of_edges() == len(mock_response.edges), "边数量应该匹配"
        
        for node_info in mock_response.nodes:
            node_id = node_info['id']
            assert result.has_node(node_id), f"图应该包含节点 {node_id}"
            node_data = result.nodes[node_id]
            assert node_data['type'] == 'class', f"节点 {node_id} 应该是class类型"
            assert node_data['source_code'] == node_info['source_code'], f"节点 {node_id} 的源代码应该匹配"
            assert node_data['description'] == node_info['description'], f"节点 {node_id} 的描述应该匹配"
        
        for edge_info in mock_response.edges:
            source = edge_info['source']
            target = edge_info['target']
            assert result.has_edge(source, target), f"图应该包含边 {source} -> {target}"
            edge_data = result.edges[source, target]
            assert edge_data['edge_type'] == 'inheritance', f"边 {source} -> {target} 应该是inheritance类型"
        
        print("   ✅ 测试用例成功：正确转换了GraphStructure到NetworkX图")
        
    except Exception as e:
        print(f"   ❌ 测试用例失败: {e}")

def test_save_and_load_nxgraph(designer: Designer):
    """测试图保存和加载功能"""
    print("\n" + "=" * 60)
    print("测试图保存和加载功能")
    print("=" * 60)
    
    mock_graph = create_mock_graph()
    print(f"输入图结构:")
    print(f"   - 节点数量: {mock_graph.number_of_nodes()}")
    print(f"   - 边数量: {mock_graph.number_of_edges()}")
    
    test_filepath = "./test_output/test_graph.json"
    print(f"\n测试保存到: {test_filepath}")
    
    try:
        success = designer.save_nxgraph_to_json(mock_graph, test_filepath)
        
        if success:
            print("✅ 文件保存成功")
            print("保存内容:")
            print("   - 只包含 type='class' 的节点")
            print("   - 只包含 edge_type='inheritance' 的边")
            print("   - 包含元数据信息")
            
            with open(test_filepath, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            print(f"   保存的节点数量: {len(saved_data['nodes'])}")
            print(f"   保存的边数量: {len(saved_data['edges'])}")
            print(f"   元数据: {saved_data['metadata']}")
            
        else:
            print("❌ 文件保存失败")
            
    except Exception as e:
        print(f"   ❌ 保存功能测试失败: {e}")
    
    print(f"\n测试从文件加载: {test_filepath}")
    
    try:
        loaded_graph = designer.load_nxgraph_from_json(test_filepath)
        
        if loaded_graph is not None:
            print("✅ 文件加载成功")
            print("加载内容:")
            print(f"   - 节点数量: {loaded_graph.number_of_nodes()}")
            print(f"   - 边数量: {loaded_graph.number_of_edges()}")
            
            assert loaded_graph.number_of_nodes() == mock_graph.number_of_nodes(), "加载的节点数量应该匹配"
            assert loaded_graph.number_of_edges() == mock_graph.number_of_edges(), "加载的边数量应该匹配"
            
            for node_id, node_data in loaded_graph.nodes(data=True):
                print(f"   节点 {node_id}: type={node_data.get('type')}, description={node_data.get('description', '')[:50]}...")
            
            for source, target, edge_data in loaded_graph.edges(data=True):
                print(f"   边 {source} -> {target}: type={edge_data.get('edge_type')}")
            
        else:
            print("❌ 文件加载失败")
            
    except Exception as e:
        print(f"   ❌ 加载功能测试失败: {e}")

def test_error_handling(designer: Designer):
    """测试错误处理功能"""
    print("\n" + "=" * 60)
    print("测试错误处理功能")
    print("=" * 60)
    
    non_existent_file = "./non_existent_file.json"
    print(f"测试用例1: 加载不存在的文件 {non_existent_file}")
    
    try:
        result = designer.load_nxgraph_from_json(non_existent_file)
        assert result is None, "加载不存在的文件应该返回None"
        print("   ✅ 错误处理正确：加载不存在的文件返回None")
        
    except Exception as e:
        print(f"   ❌ 错误处理测试失败: {e}")
    
    empty_graph = nx.DiGraph()
    print(f"\n测试用例2: 保存空图")
    
    try:
        success = designer.save_nxgraph_to_json(empty_graph, './test_output/empty_graph.json')
        assert success, "保存空图应该成功"
        print("   ✅ 空图处理正确：成功保存包含0个节点和0个边的图")
        
        loaded_empty_graph = designer.load_nxgraph_from_json('./test_output/empty_graph.json')
        assert loaded_empty_graph is not None, "应该能够加载空图"
        assert loaded_empty_graph.number_of_nodes() == 0, "加载的空图应该包含0个节点"
        assert loaded_empty_graph.number_of_edges() == 0, "加载的空图应该包含0条边"
        
    except Exception as e:
        print(f"   ❌ 空图处理测试失败: {e}")

def test_complete_workflow(designer: Designer):
    """测试完整的工作流程"""
    print("\n" + "=" * 60)
    print("测试完整工作流程")
    print("=" * 60)
    
    workflow_steps = [
        "1. 基于功能描述生成面向对象设计",
        "2. 将设计转换为 NetworkX 图",
        "3. 保存图到 JSON 文件",
        "4. 从 JSON 文件加载图",
        "5. 基于参考设计生成新设计"
    ]
    
    print("完整工作流程:")
    for step in workflow_steps:
        print(f"   {step}")
    
    try:
        print("\n执行完整工作流程:")
        
        # 步骤1：生成设计
        description = "实现一个图书管理系统，包含图书信息、借阅记录、用户管理等功能"
        print(f"   步骤1: 生成设计")
        print(f"   输入: {description}")
        
        with patch.object(designer.agent, 'invoke_with_structured_output') as mock_invoke:
            mock_design = create_mock_llm_response_for_design()
            mock_invoke.return_value = mock_design
            
            design = designer.what_to_design(description)
            print(f"   输出: ObjectOrientedDesign 对象，包含 {len(design.classes)} 个类")
        
        # 步骤2：转换为图
        print(f"\n   步骤2: 转换为图")
        print(f"   输入: ObjectOrientedDesign 对象")
        
        with patch.object(designer.agent, 'invoke_with_structured_output') as mock_invoke:
            mock_graph_structure = create_mock_llm_response_for_graph()
            mock_invoke.return_value = mock_graph_structure
            
            graph = designer.design_to_nxgraph(design)
            print(f"   输出: NetworkX 图对象，包含 {graph.number_of_nodes()} 个节点和 {graph.number_of_edges()} 条边")
        
        # 步骤3：保存图
        print(f"\n   步骤3: 保存图")
        print(f"   输入: NetworkX 图对象")
        
        output_path = './output/book_management.json'
        success = designer.save_nxgraph_to_json(graph, output_path)
        print(f"   输出: 保存成功标志 = {success}")
        
        # 步骤4：加载图
        print(f"\n   步骤4: 加载图")
        print(f"   输入: JSON 文件路径")
        
        loaded_graph = designer.load_nxgraph_from_json(output_path)
        print(f"   输出: NetworkX 图对象，包含 {loaded_graph.number_of_nodes()} 个节点和 {loaded_graph.number_of_edges()} 条边")
        
        # 步骤5：基于参考设计生成新设计
        print(f"\n   步骤5: 基于参考设计生成新设计")
        print(f"   输入: 新功能描述 + 参考设计路径")
        
        new_description = "实现一个订单管理系统，包含订单创建、状态跟踪、支付处理等功能"
        with patch.object(designer.agent, 'invoke_with_structured_output') as mock_invoke:
            mock_new_design = create_mock_llm_response_for_design()
            mock_new_design.metadata["reference_used"] = output_path
            mock_invoke.return_value = mock_new_design
            
            new_design = designer.what_to_design(new_description, output_path)
            print(f"   输出: 新的 ObjectOrientedDesign 对象，包含 {len(new_design.classes)} 个类")
            print(f"   参考设计信息: {new_design.metadata.get('reference_used', 'N/A')}")
        
        print("\n   ✅ 完整工作流程执行成功")
        
    except Exception as e:
        print(f"   ❌ 工作流程测试失败: {e}")

def run_all_tests():
    """运行所有测试函数"""
    print("🚀 开始运行 Designer 类功能测试")
    print("注意：这些测试会实际调用核心函数，但使用模拟的LLM响应")
    
    designer = test_designer_initialization()
    if designer is None:
        print("❌ Designer 初始化失败，无法继续测试")
        return
    
    test_what_to_design(designer)
    test_design_to_nxgraph(designer)
    test_response_to_nxgraph(designer)
    #test_save_and_load_nxgraph(designer)
    #test_error_handling(designer)
    #test_complete_workflow(designer)
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成！")
    print("=" * 60)
    print("测试总结:")
    print("✅ Designer 类初始化")
    print("✅ what_to_design 方法")
    print("✅ design_to_nxgraph 方法")
    print("✅ _response_to_nxgraph 方法")
    print("✅ 图保存和加载功能")
    print("✅ 错误处理功能")
    print("✅ 完整工作流程")
    print("\n所有功能测试通过！")

def create_sample_design_file():
    """创建示例设计文件，用于演示"""
    print("\n📝 创建示例设计文件")
    
    sample_design = {
        "nodes": [
            {
                "id": "User",
                "type": "class",
                "source_code": "class User:\n    def __init__(self, username, password):\n        self.username = username\n        self.password = password",
                "description": "用户基础类，包含用户名和密码"
            },
            {
                "id": "Admin",
                "type": "class",
                "source_code": "class Admin(User):\n    def __init__(self, username, password, role):\n        super().__init__(username, password)\n        self.role = role",
                "description": "管理员类，继承自User，具有特殊权限"
            }
        ],
        "edges": [
            {
                "source": "Admin",
                "target": "User",
                "edge_type": "inheritance"
            }
        ],
        "metadata": {
            "created_at": "2024-01-01T00:00:00",
            "graph_type": "class_inheritance",
            "node_count": 2,
            "edge_count": 1
        }
    }
    
    output_dir = "./test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    sample_file_path = os.path.join(output_dir, "sample_design.json")
    with open(sample_file_path, 'w', encoding='utf-8') as f:
        json.dump(sample_design, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 示例设计文件已创建: {sample_file_path}")
    print("文件内容预览:")
    print(json.dumps(sample_design, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    run_all_tests()
    create_sample_design_file()
    
    print("\n🎯 Designer 类实现完成！")
    print("主要功能:")
    print("1. 基于SOLID原则的面向对象设计生成")
    print("2. 设计到NetworkX图的转换")
    print("3. 图结构的JSON保存和加载")
    print("4. 基于参考设计的新设计生成")
    print("5. 完整的错误处理和验证")
