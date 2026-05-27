import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


class EdgeExtractor:
    """
    仅针对边(edges)的轻量工具：
    - 一次性加载 JSON 中的 edges（不使用流式解析）
    - 按类型过滤、按正则匹配 source/target
    - 从 edges 中抽取唯一的节点列表（source/target/both）
    - 列表差集

    去重策略：优先按 id；若无 id，用 (source, target, type) 复合键。
    """

    def __init__(self, json_path: str):
        self.json_path = json_path
        self._edges: List[Dict[str, Any]] = []
        self._loaded: bool = False

    def load_edges(self) -> bool:
        """
        一次性读取 JSON 并将 'edges' 加载到内存。

        Returns:
            bool: 是否加载成功
        """
        if not os.path.exists(self.json_path):
            return False

        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return False

        # 过滤掉 source == target 的边
        edges = [e for e in data.get('edges', []) if e.get('source') != e.get('target')]

        self._edges = edges
        self._loaded = True
        return True

    def get_edges_by_type(self, edge_type: str) -> List[Dict[str, Any]]:
        """按字符串的边类型过滤返回匹配的边。"""
        self._ensure_loaded()
        return [edge for edge in self._edges if edge.get('type') == edge_type]

    def search_edges(
        self,
        source_pattern: Optional[str] = None,
        target_pattern: Optional[str] = None,
        flags: int = 0,
        edge_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        使用正则对 source/target 进行匹配；可选按字符串类型集合限制。

        Args:
            source_pattern: 源节点正则（None 表示不限制）
            target_pattern: 目标节点正则（None 表示不限制）
            flags: re 编译标志，如 re.IGNORECASE
            edge_type: 边类型
        """
        self._ensure_loaded()

        src_re = re.compile(source_pattern, flags) if source_pattern else None
        tgt_re = re.compile(target_pattern, flags) if target_pattern else None

        results: List[Dict[str, Any]] = []
        for edge in self._edges:
            if edge_type and edge.get('type') != edge_type:
                continue
            if src_re and not src_re.search(edge.get('source', '') or ''):
                continue
            if tgt_re and not tgt_re.search(edge.get('target', '') or ''):
                continue
            results.append(edge)

        return results

    def unique_nodes(self, edges: List[Dict[str, Any]], mode: str = 'both') -> List[str]:
        """
        从 edges 中抽取唯一节点列表。

        Args:
            mode: 'source' | 'target' | 'both'
        """
        self._ensure_loaded()

        unique: Set[str] = set()
        if mode in ('source', 'both'):
            for edge in edges:
                s = edge.get('source')
                if s is not None:
                    unique.add(s)
        if mode in ('target', 'both'):
            for edge in edges:
                t = edge.get('target')
                if t is not None:
                    unique.add(t)

        return list(unique)

    @staticmethod
    def difference(a: Iterable[str], b: Iterable[str]) -> List[str]:
        """返回 a 中不在 b 的元素；结果按去重后的 a 的集合差集给出。"""
        set_b = set(b)
        return [x for x in set(a) if x not in set_b]

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            raise RuntimeError("Edges not loaded. Call load_edges() first.")

    # ---------------------------
    # Graph utilities (minimal)
    # ---------------------------
    def _dedupe_edges(self, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """去重：优先按 id；否则按 (source, target, type)。"""
        seen: Set[Tuple[Any, ...]] = set()
        unique: List[Dict[str, Any]] = []
        for e in edges:
            eid = e.get('id')
            if eid is not None:
                key = ('id', eid)
            else:
                key = (
                    'triple',
                    e.get('source'),
                    e.get('target'),
                    e.get('type'),
                )
            if key in seen:
                continue
            seen.add(key)
            unique.append(e)
        return unique

    def _build_graph(self, edges: List[Dict[str, Any]]) -> Tuple[Set[str], Dict[str, List[str]], Dict[str, int]]:
        """从边列表构建节点集合、邻接表与入度表。"""
        nodes: Set[str] = set()
        for e in edges:
            s, t = e.get('source'), e.get('target')
            if s is not None:
                nodes.add(s)
            if t is not None:
                nodes.add(t)

        adj: Dict[str, List[str]] = {u: [] for u in nodes}
        in_degree: Dict[str, int] = {u: 0 for u in nodes}

        for e in edges:
            s, t = e.get('source'), e.get('target')
            if s is None or t is None:
                continue
            adj.setdefault(s, []).append(t)
            in_degree[t] = in_degree.get(t, 0) + 1
            in_degree.setdefault(s, 0)

        return nodes, adj, in_degree

    def topo_sort(self, edges: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """
        在无环时返回拓扑序；若有环则抛出 ValueError，并输出环的路径。
        """
        self._ensure_loaded()
        use_edges = list(self._edges) if edges is None else list(edges)
        use_edges = [e for e in use_edges if e.get('source') != e.get('target')]
        use_edges = self._dedupe_edges(use_edges)

        nodes, adj, in_degree = self._build_graph(use_edges)
        from collections import deque

        # 拓扑排序
        q = deque([u for u in nodes if in_degree.get(u, 0) == 0])
        order: List[str] = []
        for_count = 0
        while q:
            u = q.popleft()
            order.append(u)
            for v in adj.get(u, []):
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    q.append(v)
            for_count += 1

        if len(order) != len(nodes):
            # 有环，输出环的路径
            # 使用DFS检测环并输出路径
            def find_cycle(adj):
                visited = set()
                stack = set()
                parent = {}

                def dfs(u):
                    visited.add(u)
                    stack.add(u)
                    for v in adj.get(u, []):
                        if v not in visited:
                            parent[v] = u
                            res = dfs(v)
                            if res:
                                return res
                        elif v in stack:
                            # 找到环，回溯路径
                            cycle = [v]
                            cur = u
                            while cur != v:
                                cycle.append(cur)
                                cur = parent[cur]
                            cycle.append(v)
                            cycle.reverse()
                            return cycle
                    stack.remove(u)
                    return None

                for node in adj:
                    if node not in visited:
                        parent[node] = None
                        res = dfs(node)
                        if res:
                            return res
                return None

            cycle_path = find_cycle(adj)
            if cycle_path:
                raise ValueError(f"Graph has a cycle; cannot produce topological order. Cycle: {' -> '.join(cycle_path)}")
            else:
                raise ValueError("Graph has a cycle; cannot produce topological order. (Cycle not found)")
        return order

    def dependency_counts(self, edges: Optional[List[Dict[str, Any]]] = None) -> List[Tuple[str, int]]:
        """
        统计每个节点的直接依赖数（唯一出边目标数量），并按数量降序、节点名升序返回。
        """
        self._ensure_loaded()
        use_edges = list(self._edges) if edges is None else list(edges)
        use_edges = [e for e in use_edges if e.get('source') != e.get('target')]
        use_edges = self._dedupe_edges(use_edges)

        nodes, adj, _ = self._build_graph(use_edges)
        counts = {u: len(set(adj.get(u, []))) for u in nodes}
        # 排序：先按数量降序，再按节点名升序，确保稳定
        sorted_items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return sorted_items


@dataclass
class FileStatus:
    """Lightweight container for file refactor metadata."""

    path: str
    in_refactor_scope: bool = False
    refactored: bool = False
    dependencies: int = 0
    header: Optional[str] = None  # Header file path (relative to base_path), or None if not found

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "in_refactor_scope": self.in_refactor_scope,
            "refactored": self.refactored,
            "dependencies": self.dependencies,
            "header": self.header if self.header is not None else "none",
        }


def _normalize_repo_path(raw_path: str) -> str:
    """
    Strip the 'file:' prefix and ensure paths are repository-relative using '/'.
    """
    cleaned = raw_path.replace('file:', '', 1)
    cleaned = cleaned.replace('\\', '/')
    return cleaned.lstrip('/')


def _resolve_repo_root(marker: str = "evox-server") -> Path:
    """
    Ascend from this file to locate the repository root (defaults to 'evox-server').
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        if parent.name == marker:
            return parent
    raise RuntimeError(f"Repository root '{marker}' not found above {current}")


def _find_header_file(input_path: str, base_path: str) -> Optional[str]:
    """
    查找同名的 .h 头文件
    
    Args:
        input_path: 输入文件路径（例如 source.cc）
        base_path: 基础路径，用于递归搜索
        
    Returns:
        头文件相对路径（相对于 base_path），如果未找到则返回 None
    """
    # 首先尝试相同位置的头文件
    header_path = os.path.splitext(input_path)[0] + '.h'
    if os.path.exists(header_path):
        # 转换为相对于 base_path 的相对路径
        try:
            rel_path = os.path.relpath(header_path, base_path)
            return rel_path.replace('\\', '/')
        except Exception:
            return None
    
    # 如果相同位置未找到，在base_path下递归搜索
    module_name = os.path.splitext(os.path.basename(input_path))[0]
    header_filename = module_name + '.h'
    
    if os.path.exists(base_path):
        for root, dirs, files in os.walk(base_path):
            if header_filename in files:
                found_header_path = os.path.join(root, header_filename)
                # 转换为相对于 base_path 的相对路径
                try:
                    rel_path = os.path.relpath(found_header_path, base_path)
                    return rel_path.replace('\\', '/')
                except Exception:
                    continue
    
    return None


def dump_file_status_json(
    target_dir: Optional[Path] = None,
    default_in_scope: bool = False,
    default_refactored: bool = False,
    base_path: Optional[str] = None,
    file_dependencies_path: Optional[str] = None,
) -> Path:
    """
    Persist file_list metadata into a JSON file for downstream consumption.

    Args:
        target_dir: Directory to place the JSON file (defaults to repo/.rag/xiaozhi/full_code).
        default_in_scope: Default value for 'in_refactor_scope'.
        default_refactored: Default value for 'refactored'.
        base_path: Base path for finding header files (defaults to PATH.BASE_PATH).
        file_dependencies_path: Path to file_dependencies.json (defaults to target_dir/file_dependencies.json).

    Returns:
        Path to the written JSON file.
    """
    # Import BASE_PATH from PATH module
    try:
        from src.core.rag.code.PATH import BASE_PATH
        if base_path is None:
            base_path = str(BASE_PATH)
    except ImportError:
        if base_path is None:
            raise ValueError("base_path must be provided if PATH module is not available")
    
    repo_root = _resolve_repo_root()
    output_dir = (
        Path(target_dir)
        if target_dir is not None
        else repo_root / ".rag" / "xiaozhi" / "full_code"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载 file_dependencies.json
    if file_dependencies_path is None:
        file_dependencies_path = output_dir / "file_dependencies.json"
    else:
        file_dependencies_path = Path(file_dependencies_path)
    
    if not file_dependencies_path.exists():
        raise FileNotFoundError(f"file_dependencies.json not found at: {file_dependencies_path}")
    
    with open(file_dependencies_path, 'r', encoding='utf-8') as f:
        file_dependencies_data = json.load(f)
    
    # 从 file_dependencies.json 中提取依赖信息
    # edges 格式: {"file_path": ["dependency1", "dependency2", ...]}
    edges = file_dependencies_data.get("edges", {})
    
    # 需要排除的文件列表（规范化后的路径）
    excluded_files = {
    }
    
    # 保留的例外路径（规范化后的路径）
    exception_path = "main/boards/atk-dnesp32s3/atk_dnesp32s3.cc"
    
    statuses = []
    # 遍历 file_dependencies.json 中的所有文件
    for file_path in sorted(edges.keys()):
        normalized_path = file_path  # file_dependencies.json 中的路径已经是规范化后的路径（无file:前缀）
        
        # 排除指定的文件
        if normalized_path in excluded_files:
            continue
        
        # 过滤掉包含 "boards" 的路径，但保留例外路径
        if "boards" not in normalized_path or normalized_path == exception_path or "common" in normalized_path:
            # 获取依赖数量
            dependency_count = len(edges[file_path])
            
            # 查找头文件路径
            full_file_path = os.path.join(base_path, normalized_path)
            header_path = _find_header_file(full_file_path, base_path)
            
            statuses.append(
                FileStatus(
                    path=normalized_path,
                    in_refactor_scope=default_in_scope,
                    refactored=default_refactored,
                    dependencies=dependency_count,
                    header=header_path,
                ).to_dict()
            )

    # 按照 dependencies 降序排序（依赖数量多的在前）
    statuses.sort(key=lambda x: x['dependencies'], reverse=True)

    output_path = output_dir / "file_status_full_code.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(statuses, f, ensure_ascii=False, indent=2)

    return output_path

file_list = [('file:main/boards/common/wifi_board.cc', 13), ('file:main/boards/esp32-s3-touch-amoled-1.8/esp32-s3-touch-amoled-1.8.cc', 13), ('file:main/boards/kevin-box-2/kevin_box_board.cc', 13), ('file:main/boards/esp32-s3-touch-lcd-3.5/esp32-s3-touch-lcd-3.5.cc', 12), ('file:main/boards/tudouzi/kevin_box_board.cc', 12), ('file:main/boards/xingzhi-cube-1.54tft-ml307/xingzhi-cube-1.54tft-ml307.cc', 12), ('file:main/boards/atk-dnesp32s3-box0/atk_dnesp32s3_box0.cc', 11), ('file:main/boards/lilygo-t-cameraplus-s3/lilygo-t-cameraplus-s3.cc', 11), ('file:main/boards/lilygo-t-circle-s3/lilygo-t-circle-s3.cc', 11), ('file:main/boards/lilygo-t-display-s3-pro-mvsrlora/lilygo-t-display-s3-pro-mvsrlora.cc', 11), ('file:main/boards/m5stack-core-s3/m5stack_core_s3.cc', 11), ('file:main/boards/magiclick-2p4/magiclick_2p4_board.cc', 11), ('file:main/boards/magiclick-2p5/magiclick_2p5_board.cc', 11), ('file:main/boards/magiclick-c3-v2/magiclick_c3_v2_board.cc', 11), ('file:main/boards/magiclick-c3/magiclick_c3_board.cc', 11), ('file:main/boards/sensecap-watcher/sensecap_watcher.cc', 11), ('file:main/boards/xingzhi-cube-0.96oled-ml307/xingzhi-cube-0.96oled-ml307.cc', 11), ('file:main/boards/xingzhi-cube-1.54tft-wifi/xingzhi-cube-1.54tft-wifi.cc', 11), ('file:main/boards/xmini-c3/xmini_c3_board.cc', 11), ('file:main/application.cc', 10), ('file:main/boards/atk-dnesp32s3m-wifi/atk_dnesp32s3m.cc', 10), ('file:main/boards/atoms3r-echo-base/atoms3r_echo_base.cc', 10), ('file:main/boards/bread-compact-ml307/compact_ml307_board.cc', 10), ('file:main/boards/du-chatx/du-chatx-wifi.cc', 10), ('file:main/boards/esp-box-lite/esp_box_lite_board.cc', 10), ('file:main/boards/mixgo-nova/mixgo-nova.cc', 10), ('file:main/boards/xingzhi-cube-0.85tft-wifi/xingzhi-cube-0.85tft-wifi.cc', 10), ('file:main/boards/xingzhi-cube-0.96oled-wifi/xingzhi-cube-0.96oled-wifi.cc', 10), ('file:main/boards/atk-dnesp32s3m-4g/atk_dnesp32s3m.cc', 9), ('file:main/boards/atoms3-echo-base/atoms3_echo_base.cc', 9), ('file:main/boards/bread-compact-wifi/compact_wifi_board.cc', 9), ('file:main/boards/common/ml307_board.cc', 9), ('file:main/boards/esp-sparkbot/esp_sparkbot_board.cc', 9), ('file:main/boards/lichuang-dev/lichuang_dev_board.cc', 9), ('file:main/boards/xingzhi-cube-0.85tft-ml307/xingzhi-cube-0.85tft-ml307.cc', 9), ('file:main/boards/atk-dnesp32s3-box/atk_dnesp32s3_box.cc', 8), ('file:main/boards/atk-dnesp32s3/atk_dnesp32s3.cc', 8), ('file:main/boards/bread-compact-esp32-lcd/esp32_bread_board_lcd.cc', 8), ('file:main/boards/bread-compact-wifi-lcd/compact_wifi_board_lcd.cc', 8), ('file:main/boards/df-k10/df_k10_board.cc', 8), ('file:main/boards/esp-box-3/esp_box3_board.cc', 8), ('file:main/boards/esp-box/esp_box_board.cc', 8), ('file:main/boards/esp32-cgc/esp32_cgc_board.cc', 8), ('file:main/boards/esp32-s3-touch-lcd-1.85c/esp32-s3-touch-lcd-1.85c.cc', 8), ('file:main/boards/kevin-box-1/kevin_box_board.cc', 8), ('file:main/boards/kevin-c3/kevin_c3_board.cc', 8), ('file:main/boards/kevin-sp-v3-dev/kevin-sp-v3_board.cc', 8), ('file:main/boards/kevin-sp-v4-dev/kevin-sp-v4_board.cc', 8), ('file:main/boards/kevin-yuying-313lcd/kevin_yuying_313lcd.cc', 8), ('file:main/boards/lichuang-c3-dev/lichuang_c3_dev_board.cc', 8), ('file:main/boards/movecall-cuican-esp32s3/movecall_cuican_esp32s3.cc', 8), ('file:main/boards/movecall-moji-esp32s3/movecall_moji_esp32s3.cc', 8), ('file:main/boards/taiji-pi-s3/taiji_pi_s3.cc', 8), ('file:main/boards/atommatrix-echo-base/atommatrix_echo_base.cc', 7), ('file:main/boards/bread-compact-esp32/esp32_bread_board.cc', 7), ('file:main/boards/doit-s3-aibox/doit_s3_aibox.cc', 7), ('file:main/boards/esp-s3-lcd-ev-board/esp-s3-lcd-ev-board.cc', 7), ('file:main/boards/esp32-s3-touch-lcd-1.46/esp32-s3-touch-lcd-1.46.cc', 7), ('file:main/boards/esp32-s3-touch-lcd-1.85/esp32-s3-touch-lcd-1.85.cc', 7), ('file:main/boards/esp32s3-korvo2-v3/esp32s3_korvo2_v3_board.cc', 7), ('file:main/boards/esp-spot-s3/esp_spot_s3_board.cc', 6), ('file:main/boards/common/dual_network_board.cc', 4), ('file:main/protocols/websocket_protocol.cc', 4), ('file:main/boards/atoms3r-cam-m12-echo-base/atoms3r_cam_m12_echo_base.cc', 3), ('file:main/iot/things/screen.cc', 3), ('file:main/ota.cc', 3), ('file:main/protocols/mqtt_protocol.cc', 3), ('file:main/boards/common/board.cc', 2), ('file:main/boards/kevin-c3/led_strip_control.cc', 2), ('file:main/display/display.cc', 2), ('file:managed_components/78__esp-wifi-connect/wifi_configuration_ap.cc', 2), ('file:main/audio_codecs/audio_codec.cc', 1), ('file:main/audio_codecs/box_audio_codec.cc', 1), ('file:main/audio_codecs/es8311_audio_codec.cc', 1), ('file:main/audio_codecs/es8374_audio_codec.cc', 1), ('file:main/audio_codecs/es8388_audio_codec.cc', 1), ('file:main/audio_processing/wake_word_detect.cc', 1), ('file:main/boards/common/axp2101.cc', 1), ('file:main/boards/common/backlight.cc', 1), ('file:main/boards/common/power_save_timer.cc', 1), ('file:main/boards/df-k10/k10_audio_codec.cc', 1), ('file:main/boards/esp-box-lite/box_audio_codec_lite.cc', 1), ('file:main/boards/esp32-s3-touch-amoled-1.8/board_control.cc', 1), ('file:main/boards/esp32-s3-touch-lcd-3.5/board_control.cc', 1), ('file:main/boards/lilygo-t-cameraplus-s3/tcamerapluss3_audio_codec.cc', 1), ('file:main/boards/lilygo-t-circle-s3/tcircles3_audio_codec.cc', 1), ('file:main/boards/lilygo-t-display-s3-pro-mvsrlora/tdisplays3promvsrlora_audio_codec.cc', 1), ('file:main/boards/m5stack-core-s3/cores3_audio_codec.cc', 1), ('file:main/boards/sensecap-watcher/sensecap_audio_codec.cc', 1), ('file:main/display/lcd_display.cc', 1), ('file:main/iot/thing.cc', 1), ('file:main/iot/thing_manager.cc', 1), ('file:main/iot/things/battery.cc', 1), ('file:main/iot/things/speaker.cc', 1), ('file:main/main.cc', 1), ('file:managed_components/78__esp-ml307/ml307_http.cc', 1), ('file:managed_components/78__esp-ml307/ml307_mqtt.cc', 1), ('file:managed_components/78__esp-ml307/ml307_ssl_transport.cc', 1), ('file:managed_components/78__esp-ml307/ml307_udp.cc', 1), ('file:managed_components/78__esp-wifi-connect/wifi_station.cc', 1), ('file:main/background_task.cc', 0), ('file:main/boards/common/button.cc', 0), ('file:main/boards/common/i2c_device.cc', 0), ('file:main/boards/common/knob.cc', 0), ('file:main/display/oled_display.cc', 0), ('file:main/led/circular_strip.cc', 0), ('file:main/protocols/protocol.cc', 0), ('file:main/settings.cc', 0), ('file:main/system_info.cc', 0), ('file:managed_components/78__esp-ml307/esp_http.cc', 0), ('file:managed_components/78__esp-ml307/esp_mqtt.cc', 0), ('file:managed_components/78__esp-ml307/esp_udp.cc', 0), ('file:managed_components/78__esp-ml307/ml307_at_modem.cc', 0), ('file:managed_components/78__esp-ml307/tcp_transport.cc', 0), ('file:managed_components/78__esp-ml307/tls_transport.cc', 0), ('file:managed_components/78__esp-ml307/web_socket.cc', 0), ('file:managed_components/78__esp-opus-encoder/opus_decoder.cc', 0), ('file:managed_components/78__esp-opus-encoder/opus_encoder.cc', 0), ('file:managed_components/78__esp-opus-encoder/opus_resampler.cc', 0), ('file:managed_components/78__esp-wifi-connect/dns_server.cc', 0), ('file:managed_components/78__esp-wifi-connect/ssid_manager.cc', 0)]

no_dependency_file_list = ['main/audio_codecs/no_audio_codec.cc', 'main/audio_processing/afe_audio_processor.cc', 'main/audio_processing/dummy_audio_processor.cc', 'main/boards/common/system_reset.cc', 'main/boards/esp-sparkbot/chassis.cc', 'main/iot/things/lamp.cc', 'main/led/gpio_led.cc', 'main/led/single_led.cc']

total_file_str = r"""
D:\Download\github\xiaozhi-esp32\main\application.cc
D:\Download\github\xiaozhi-esp32\main\background_task.cc
D:\Download\github\xiaozhi-esp32\main\main.cc
D:\Download\github\xiaozhi-esp32\main\ota.cc
D:\Download\github\xiaozhi-esp32\main\settings.cc
D:\Download\github\xiaozhi-esp32\main\settings_refactored.cc
D:\Download\github\xiaozhi-esp32\main\system_info.cc
D:\Download\github\xiaozhi-esp32\main\audio_codecs\audio_codec.cc
D:\Download\github\xiaozhi-esp32\main\audio_codecs\audio_codec_refactored.cc
D:\Download\github\xiaozhi-esp32\main\audio_codecs\box_audio_codec.cc
D:\Download\github\xiaozhi-esp32\main\audio_codecs\es8311_audio_codec.cc
D:\Download\github\xiaozhi-esp32\main\audio_codecs\es8374_audio_codec.cc
D:\Download\github\xiaozhi-esp32\main\audio_codecs\es8388_audio_codec.cc
D:\Download\github\xiaozhi-esp32\main\audio_codecs\no_audio_codec.cc
D:\Download\github\xiaozhi-esp32\main\audio_processing\afe_audio_processor.cc
D:\Download\github\xiaozhi-esp32\main\audio_processing\dummy_audio_processor.cc
D:\Download\github\xiaozhi-esp32\main\audio_processing\wake_word_detect.cc
D:\Download\github\xiaozhi-esp32\main\boards\atk-dnesp32s3\atk_dnesp32s3.cc
D:\Download\github\xiaozhi-esp32\main\boards\atk-dnesp32s3-box\atk_dnesp32s3_box.cc
D:\Download\github\xiaozhi-esp32\main\boards\atk-dnesp32s3-box0\atk_dnesp32s3_box0.cc
D:\Download\github\xiaozhi-esp32\main\boards\atk-dnesp32s3m-4g\atk_dnesp32s3m.cc
D:\Download\github\xiaozhi-esp32\main\boards\atk-dnesp32s3m-wifi\atk_dnesp32s3m.cc
D:\Download\github\xiaozhi-esp32\main\boards\atommatrix-echo-base\atommatrix_echo_base.cc
D:\Download\github\xiaozhi-esp32\main\boards\atoms3-echo-base\atoms3_echo_base.cc
D:\Download\github\xiaozhi-esp32\main\boards\atoms3r-cam-m12-echo-base\atoms3r_cam_m12_echo_base.cc
D:\Download\github\xiaozhi-esp32\main\boards\atoms3r-echo-base\atoms3r_echo_base.cc
D:\Download\github\xiaozhi-esp32\main\boards\bread-compact-esp32\esp32_bread_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\bread-compact-esp32-lcd\esp32_bread_board_lcd.cc
D:\Download\github\xiaozhi-esp32\main\boards\bread-compact-ml307\compact_ml307_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\bread-compact-wifi\compact_wifi_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\bread-compact-wifi-lcd\compact_wifi_board_lcd.cc
D:\Download\github\xiaozhi-esp32\main\boards\common\axp2101.cc
D:\Download\github\xiaozhi-esp32\main\boards\common\backlight.cc
D:\Download\github\xiaozhi-esp32\main\boards\common\board.cc
D:\Download\github\xiaozhi-esp32\main\boards\common\button.cc
D:\Download\github\xiaozhi-esp32\main\boards\common\dual_network_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\common\i2c_device.cc
D:\Download\github\xiaozhi-esp32\main\boards\common\knob.cc
D:\Download\github\xiaozhi-esp32\main\boards\common\ml307_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\common\power_save_timer.cc
D:\Download\github\xiaozhi-esp32\main\boards\common\system_reset.cc
D:\Download\github\xiaozhi-esp32\main\boards\common\wifi_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\df-k10\df_k10_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\df-k10\k10_audio_codec.cc
D:\Download\github\xiaozhi-esp32\main\boards\doit-s3-aibox\doit_s3_aibox.cc
D:\Download\github\xiaozhi-esp32\main\boards\du-chatx\du-chatx-wifi.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp-box\esp_box_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp-box-3\esp_box3_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp-box-lite\box_audio_codec_lite.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp-box-lite\esp_box_lite_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp-s3-lcd-ev-board\esp-s3-lcd-ev-board.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp-sparkbot\chassis.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp-sparkbot\esp_sparkbot_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp-spot-s3\esp_spot_s3_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp32-cgc\esp32_cgc_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp32-s3-touch-amoled-1.8\board_control.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp32-s3-touch-amoled-1.8\esp32-s3-touch-amoled-1.8.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp32-s3-touch-lcd-1.46\esp32-s3-touch-lcd-1.46.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp32-s3-touch-lcd-1.85\esp32-s3-touch-lcd-1.85.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp32-s3-touch-lcd-1.85c\esp32-s3-touch-lcd-1.85c.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp32-s3-touch-lcd-3.5\board_control.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp32-s3-touch-lcd-3.5\esp32-s3-touch-lcd-3.5.cc
D:\Download\github\xiaozhi-esp32\main\boards\esp32s3-korvo2-v3\esp32s3_korvo2_v3_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\kevin-box-1\kevin_box_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\kevin-box-2\kevin_box_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\kevin-c3\kevin_c3_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\kevin-c3\led_strip_control.cc
D:\Download\github\xiaozhi-esp32\main\boards\kevin-sp-v3-dev\kevin-sp-v3_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\kevin-sp-v4-dev\kevin-sp-v4_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\kevin-yuying-313lcd\kevin_yuying_313lcd.cc
D:\Download\github\xiaozhi-esp32\main\boards\lichuang-c3-dev\lichuang_c3_dev_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\lichuang-dev\lichuang_dev_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\lilygo-t-cameraplus-s3\lilygo-t-cameraplus-s3.cc
D:\Download\github\xiaozhi-esp32\main\boards\lilygo-t-cameraplus-s3\tcamerapluss3_audio_codec.cc
D:\Download\github\xiaozhi-esp32\main\boards\lilygo-t-circle-s3\lilygo-t-circle-s3.cc
D:\Download\github\xiaozhi-esp32\main\boards\lilygo-t-circle-s3\tcircles3_audio_codec.cc
D:\Download\github\xiaozhi-esp32\main\boards\lilygo-t-display-s3-pro-mvsrlora\lilygo-t-display-s3-pro-mvsrlora.cc
D:\Download\github\xiaozhi-esp32\main\boards\lilygo-t-display-s3-pro-mvsrlora\tdisplays3promvsrlora_audio_codec.cc
D:\Download\github\xiaozhi-esp32\main\boards\m5stack-core-s3\cores3_audio_codec.cc
D:\Download\github\xiaozhi-esp32\main\boards\m5stack-core-s3\m5stack_core_s3.cc
D:\Download\github\xiaozhi-esp32\main\boards\magiclick-2p4\magiclick_2p4_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\magiclick-2p5\magiclick_2p5_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\magiclick-c3\magiclick_c3_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\magiclick-c3-v2\magiclick_c3_v2_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\mixgo-nova\mixgo-nova.cc
D:\Download\github\xiaozhi-esp32\main\boards\movecall-cuican-esp32s3\movecall_cuican_esp32s3.cc
D:\Download\github\xiaozhi-esp32\main\boards\movecall-moji-esp32s3\movecall_moji_esp32s3.cc
D:\Download\github\xiaozhi-esp32\main\boards\sensecap-watcher\sensecap_audio_codec.cc
D:\Download\github\xiaozhi-esp32\main\boards\sensecap-watcher\sensecap_watcher.cc
D:\Download\github\xiaozhi-esp32\main\boards\taiji-pi-s3\taiji_pi_s3.cc
D:\Download\github\xiaozhi-esp32\main\boards\tudouzi\kevin_box_board.cc
D:\Download\github\xiaozhi-esp32\main\boards\xingzhi-cube-0.85tft-ml307\xingzhi-cube-0.85tft-ml307.cc
D:\Download\github\xiaozhi-esp32\main\boards\xingzhi-cube-0.85tft-wifi\xingzhi-cube-0.85tft-wifi.cc
D:\Download\github\xiaozhi-esp32\main\boards\xingzhi-cube-0.96oled-ml307\xingzhi-cube-0.96oled-ml307.cc
D:\Download\github\xiaozhi-esp32\main\boards\xingzhi-cube-0.96oled-wifi\xingzhi-cube-0.96oled-wifi.cc
D:\Download\github\xiaozhi-esp32\main\boards\xingzhi-cube-1.54tft-ml307\xingzhi-cube-1.54tft-ml307.cc
D:\Download\github\xiaozhi-esp32\main\boards\xingzhi-cube-1.54tft-wifi\xingzhi-cube-1.54tft-wifi.cc
D:\Download\github\xiaozhi-esp32\main\boards\xmini-c3\xmini_c3_board.cc
D:\Download\github\xiaozhi-esp32\main\display\display.cc
D:\Download\github\xiaozhi-esp32\main\display\lcd_display.cc
D:\Download\github\xiaozhi-esp32\main\display\oled_display.cc
D:\Download\github\xiaozhi-esp32\main\iot\thing.cc
D:\Download\github\xiaozhi-esp32\main\iot\thing_manager.cc
D:\Download\github\xiaozhi-esp32\main\iot\things\battery.cc
D:\Download\github\xiaozhi-esp32\main\iot\things\lamp.cc
D:\Download\github\xiaozhi-esp32\main\iot\things\screen.cc
D:\Download\github\xiaozhi-esp32\main\iot\things\speaker.cc
D:\Download\github\xiaozhi-esp32\main\led\circular_strip.cc
D:\Download\github\xiaozhi-esp32\main\led\gpio_led.cc
D:\Download\github\xiaozhi-esp32\main\led\single_led.cc
D:\Download\github\xiaozhi-esp32\main\protocols\mqtt_protocol.cc
D:\Download\github\xiaozhi-esp32\main\protocols\protocol.cc
D:\Download\github\xiaozhi-esp32\main\protocols\websocket_protocol.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-ml307\esp_http.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-ml307\esp_mqtt.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-ml307\esp_udp.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-ml307\ml307_at_modem.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-ml307\ml307_http.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-ml307\ml307_mqtt.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-ml307\ml307_ssl_transport.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-ml307\ml307_udp.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-ml307\tcp_transport.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-ml307\tls_transport.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-ml307\web_socket.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-opus-encoder\opus_decoder.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-opus-encoder\opus_encoder.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-opus-encoder\opus_resampler.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-wifi-connect\dns_server_v1.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-wifi-connect\dns_server_v2.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-wifi-connect\ssid_manager.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-wifi-connect\wifi_configuration_ap.cc
D:\Download\github\xiaozhi-esp32\managed_components\78__esp-wifi-connect\wifi_station.cc
"""

def find_missing_files(file_list, total_file_list):
    """
    判断total file list中的哪些文件在file_list中未被包含
    
    Args:
        file_list: 包含(file_path, count)元组的列表
        total_file_list: 包含完整文件路径的字符串列表
    
    Returns:
        List[str]: 在total_file_list中但不在file_list中的文件路径列表
    """
    # 从file_list中提取文件路径，去掉'file:'前缀
    file_list_paths = set()
    for file_path, count in file_list:
        # 去掉'file:'前缀
        clean_path = file_path.replace('file:', '')
        file_list_paths.add(clean_path)
    
    # 从total_file_list中提取相对路径
    total_file_paths = set()
    for full_path in total_file_list:
        # 提取相对路径部分（去掉绝对路径前缀）
        if 'xiaozhi-esp32\\' in full_path:
            relative_path = full_path.split('xiaozhi-esp32\\')[1]
            # 将Windows路径分隔符转换为Unix风格
            relative_path = relative_path.replace('\\', '/')
            total_file_paths.add(relative_path)
    
    # 找出在total_file_paths中但不在file_list_paths中的文件
    missing_files = total_file_paths - file_list_paths
    
    return sorted(list(missing_files))


def filter_embedding_json(
    input_path: str,
    output_path: str,
) -> bool:
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    filtered_data = {}
    for key, value in data.items():
        if "boards" in key and "/atk-dnesp32s3/" not in key:
            continue
        filtered_data[key] = value

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # json_path = dump_file_status_json()
    # print(f"File status JSON written to: {json_path}")
    filter_embedding_json("D:/Download/github/evox-ai/evox-server/.rag/xiaozhi/full_code/functions_what_graph_concurrent_emb.json", "D:/Download/github/evox-ai/evox-server/.rag/xiaozhi/full_code/functions_what_graph_clean_emb.json")