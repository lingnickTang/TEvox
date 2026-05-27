# 使用networkx库构建有向图
import networkx as nx
from src.base import DefaultConfig

graph = nx.DiGraph()
#############################################################################
# ssid_manager

# 添加 SsidManager 相关的节点
graph.add_node(
    "struct SsidItem",
    body="""struct SsidItem {
    std::string ssid;
    std::string password;
};""",
)

graph.add_node(
    "class SsidManager",
    body="""class SsidManager {
public:
    static SsidManager& GetInstance();
    void AddSsid(const std::string& ssid, const std::string& password);
    void RemoveSsid(int index);
    void SetDefaultSsid(int index);
    void Clear();
    const std::vector<SsidItem>& GetSsidList() const { return ssid_list_; }

private:
    SsidManager();
    ~SsidManager();

    void LoadFromNvs();
    void SaveToNvs();

    std::vector<SsidItem> ssid_list_;
};""",
)

graph.add_node(
    "SsidManager& SsidManager::GetInstance()",
    body="""SsidManager& SsidManager::GetInstance() {
    static SsidManager instance;
    return instance;
}""",
)

graph.add_node(
    "SsidManager::SsidManager()",
    body="""SsidManager::SsidManager() {
    LoadFromNvs();
}""",
)

graph.add_node(
    "SsidManager::~SsidManager()",
    body="SsidManager::~SsidManager() { }",
)

graph.add_node(
    "void SsidManager::Clear()",
    body="""void SsidManager::Clear() {
    ssid_list_.clear();
    SaveToNvs();
}""",
)

graph.add_node(
    "void SsidManager::LoadFromNvs()",
    body="""void SsidManager::LoadFromNvs() {
    ssid_list_.clear();

    // Load ssid and password from NVS from namespace "wifi"
    // ssid, ssid1, ssid2, ... ssid9
    // password, password1, password2, ... password9
    nvs_handle_t nvs_handle;
    auto ret = nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs_handle);
    if (ret != ESP_OK) {
        // The namespace doesn't exist, just return
        ESP_LOGW(TAG, "NVS namespace %s doesn't exist", NVS_NAMESPACE);
        return;
    }
    for (int i = 0; i < 10; i++) {
        std::string ssid_key = "ssid";
        if (i > 0) {
            ssid_key += std::to_string(i);
        }
        std::string password_key = "password";
        if (i > 0) {
            password_key += std::to_string(i);
        }
        
        char ssid[33];
        char password[65];
        size_t length = sizeof(ssid);
        if (nvs_get_str(nvs_handle, ssid_key.c_str(), ssid, &length) != ESP_OK) {
            continue;
        }
        length = sizeof(password);
        if (nvs_get_str(nvs_handle, password_key.c_str(), password, &length) != ESP_OK) {
            continue;
        }
        ssid_list_.push_back({ssid, password});
    }
    nvs_close(nvs_handle);
}""",
)

graph.add_node(
    "void SsidManager::SaveToNvs()",
    body="""void SsidManager::SaveToNvs() {
    nvs_handle_t nvs_handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READWRITE, &nvs_handle));
    for (int i = 0; i < 10; i++) {
        std::string ssid_key = "ssid";
        if (i > 0) {
            ssid_key += std::to_string(i);
        }
        std::string password_key = "password";
        if (i > 0) {
            password_key += std::to_string(i);
        }
        
        if (i < ssid_list_.size()) {
            nvs_set_str(nvs_handle, ssid_key.c_str(), ssid_list_[i].ssid.c_str());
            nvs_set_str(nvs_handle, password_key.c_str(), ssid_list_[i].password.c_str());
        } else {
            nvs_erase_key(nvs_handle, ssid_key.c_str());
            nvs_erase_key(nvs_handle, password_key.c_str());
        }
    }
    nvs_commit(nvs_handle);
    nvs_close(nvs_handle);
}""",
)

graph.add_node(
    "void SsidManager::AddSsid(const std::string& ssid, const std::string& password)",
    body="""void SsidManager::AddSsid(const std::string& ssid, const std::string& password) {
    for (auto& item : ssid_list_) {
        ESP_LOGI(TAG, "compare [%s:%d] [%s:%d]", item.ssid.c_str(), item.ssid.size(), ssid.c_str(), ssid.size());
        if (item.ssid == ssid) {
            ESP_LOGW(TAG, "SSID %s already exists, overwrite it", ssid.c_str());
            item.password = password;
            SaveToNvs();
            return;
        }
    }

    if (ssid_list_.size() >= MAX_WIFI_SSID_COUNT) {
        ESP_LOGW(TAG, "SSID list is full, pop one");
        ssid_list_.pop_back();
    }
    // Add the new ssid to the front of the list
    ssid_list_.insert(ssid_list_.begin(), {ssid, password});
    SaveToNvs();
}""",
)

graph.add_node(
    "void SsidManager::RemoveSsid(int index)",
    body="""void SsidManager::RemoveSsid(int index) {
    if (index < 0 || index >= ssid_list_.size()) {
        ESP_LOGW(TAG, "Invalid index %d", index);
        return;
    }
    ssid_list_.erase(ssid_list_.begin() + index);
    SaveToNvs();
}""",
)

graph.add_node(
    "void SsidManager::SetDefaultSsid(int index)",
    body="""void SsidManager::SetDefaultSsid(int index) {
    if (index < 0 || index >= ssid_list_.size()) {
        ESP_LOGW(TAG, "Invalid index %d", index);
        return;
    }
    // Move the ssid at index to the front of the list
    auto item = ssid_list_[index];
    ssid_list_.erase(ssid_list_.begin() + index);
    ssid_list_.insert(ssid_list_.begin(), item);
    SaveToNvs();
}""",
)

# 添加 SsidManager 相关的边
graph.add_edge("SsidManager& SsidManager::GetInstance()", "class SsidManager")
graph.add_edge("SsidManager::SsidManager()", "class SsidManager")
graph.add_edge("SsidManager::~SsidManager()", "class SsidManager")
graph.add_edge("void SsidManager::Clear()", "class SsidManager")
graph.add_edge("void SsidManager::LoadFromNvs()", "class SsidManager")
graph.add_edge("void SsidManager::SaveToNvs()", "class SsidManager")
graph.add_edge("void SsidManager::AddSsid(const std::string& ssid, const std::string& password)", "class SsidManager")
graph.add_edge("void SsidManager::RemoveSsid(int index)", "class SsidManager")
graph.add_edge("void SsidManager::SetDefaultSsid(int index)", "class SsidManager")

# 添加方法之间的调用关系
graph.add_edge("void SsidManager::AddSsid(const std::string& ssid, const std::string& password)", "void SsidManager::SaveToNvs()")
graph.add_edge("void SsidManager::RemoveSsid(int index)", "void SsidManager::SaveToNvs()")
graph.add_edge("void SsidManager::SetDefaultSsid(int index)", "void SsidManager::SaveToNvs()")
graph.add_edge("void SsidManager::Clear()", "void SsidManager::SaveToNvs()")
graph.add_edge("SsidManager::SsidManager()", "void SsidManager::LoadFromNvs()")

# 添加数据结构关系
graph.add_edge("struct SsidItem", "class SsidManager")

#############################################################################
# wifi_station

# graph.add_node(
#     "struct WifiApRecord",
#     body="""struct WifiApRecord {
#     std::string ssid;
#     std::string password;
#     int channel;
#     wifi_auth_mode_t authmode;
#     uint8_t bssid[6];
# };""",
# )

# graph.add_node(
#     "class WifiStation",
#     body="""class WifiStation {
# public:
#     static WifiStation& GetInstance();
#     void AddAuth(const std::string &&ssid, const std::string &&password);
#     void Start();
#     void Stop();
#     bool IsConnected();
#     bool WaitForConnected(int timeout_ms = 10000);
#     int8_t GetRssi();
#     std::string GetSsid() const { return ssid_; }
#     std::string GetIpAddress() const { return ip_address_; }
#     uint8_t GetChannel();
#     void SetPowerSaveMode(bool enabled);

#     void OnConnect(std::function<void(const std::string& ssid)> on_connect);
#     void OnConnected(std::function<void(const std::string& ssid)> on_connected);
#     void OnScanBegin(std::function<void()> on_scan_begin);
#     void OnDisconnect(std::function<void()> on_disconnect);

# private:
#     WifiStation();
#     ~WifiStation();
#     WifiStation(const WifiStation&) = delete;
#     WifiStation& operator=(const WifiStation&) = delete;

#     EventGroupHandle_t event_group_;
#     esp_timer_handle_t timer_handle_ = nullptr;
#     esp_event_handler_instance_t instance_any_id_ = nullptr;
#     esp_event_handler_instance_t instance_got_ip_ = nullptr;
#     std::string ssid_;
#     std::string password_;
#     std::string ip_address_;
#     int reconnect_count_ = 0;
#     std::function<void(const std::string& ssid)> on_connect_;
#     std::function<void(const std::string& ssid)> on_connected_;
#     std::function<void()> on_scan_begin_;
#     std::function<void()> on_disconnect_;
#     std::vector<WifiApRecord> connect_queue_;

#     void HandleScanResult();
#     void StartConnect();
#     static void WifiEventHandler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data);
#     static void IpEventHandler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data);
# };""",
# )


# graph.add_node(
#     "WifiStation& WifiStation::GetInstance()",
#     body="""WifiStation& WifiStation::GetInstance() {
#     static WifiStation instance;
#     return instance;}""",
# )
# graph.add_node(
#     "WifiStation::WifiStation()",
#     body="WifiStation::WifiStation() { event_group_ = xEventGroupCreate(); }",
# )
# graph.add_node(
#     "WifiStation::~WifiStation()",
#     body="WifiStation::~WifiStation() { vEventGroupDelete(event_group_); }",
# )
# graph.add_node(
#     "void WifiStation::AddAuth(const std::string &&ssid, const std::string &&password)",
#     body="""void WifiStation::AddAuth(const std::string &&ssid, const std::string &&password) {
#     auto& ssid_manager = SsidManager::GetInstance();
#     ssid_manager.AddSsid(ssid, password);}""",
# )
# graph.add_node(
#     "void WifiStation::Stop()",
#     body="""void WifiStation::Stop() {
#     if (timer_handle_ != nullptr) {
#         esp_timer_stop(timer_handle_);
#         esp_timer_delete(timer_handle_);
#         timer_handle_ = nullptr;
#     }
#     ESP_ERROR_CHECK(esp_wifi_stop());
#     ESP_ERROR_CHECK(esp_wifi_deinit());
#     if (instance_any_id_ != nullptr) {
#         ESP_ERROR_CHECK(esp_event_handler_instance_unregister(WIFI_EVENT, ESP_EVENT_ANY_ID, instance_any_id_));
#         instance_any_id_ = nullptr;
#     }
#     if (instance_got_ip_ != nullptr) {
#         ESP_ERROR_CHECK(esp_event_handler_instance_unregister(IP_EVENT, IP_EVENT_STA_GOT_IP, instance_got_ip_));
#         instance_got_ip_ = nullptr;
#     }}""",
# )
# graph.add_node(
#     "void WifiStation::OnScanBegin(std::function<void()> on_scan_begin)",
#     body="""void WifiStation::OnScanBegin(std::function<void()> on_scan_begin) {
#     on_scan_begin_ = on_scan_begin;}""",
# )
# graph.add_node(
#     "void WifiStation::OnConnect(std::function<void(const std::string& ssid)> on_connect)",
#     body="""void WifiStation::OnConnect(std::function<void(const std::string& ssid)> on_connect) {
#     on_connect_ = on_connect;}""",
# )
# graph.add_node(
#     "void WifiStation::OnConnected(std::function<void(const std::string& ssid)> on_connected)",
#     body="""void WifiStation::OnConnected(std::function<void(const std::string& ssid)> on_connected) {
#     on_connected_ = on_connected;}""",
# )
# graph.add_node(
#     "void WifiStation::OnDisconnect(std::function<void()> on_disconnect)",
#     body="""void WifiStation::OnDisconnect(std::function<void()> on_disconnect) {
#     on_disconnect_ = on_disconnect;}""",
# )


# graph.add_node(
#     "void WifiStation::Start()",
#     body="""void WifiStation::Start() {
#     ESP_ERROR_CHECK(esp_netif_init());
#     ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &WifiStation::WifiEventHandler, this, &instance_any_id_));
#     ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &WifiStation::IpEventHandler, this, &instance_got_ip_));
#     esp_netif_create_default_wifi_sta();
#     wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
#     cfg.nvs_enable = false;
#     ESP_ERROR_CHECK(esp_wifi_init(&cfg));
#     ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
#     ESP_ERROR_CHECK(esp_wifi_start());
#     esp_timer_create_args_t timer_args = {
#         .callback = [](void* arg) { esp_wifi_scan_start(nullptr, false); },
#         .arg = this,
#         .dispatch_method = ESP_TIMER_TASK,
#         .name = "WiFiScanTimer",
#         .skip_unhandled_events = true
#     };
#     ESP_ERROR_CHECK(esp_timer_create(&timer_args, &timer_handle_));}""",
# )
# graph.add_node(
#     "bool WifiStation::WaitForConnected(int timeout_ms)",
#     body="""bool WifiStation::WaitForConnected(int timeout_ms) {
#     auto bits = xEventGroupWaitBits(event_group_, WIFI_EVENT_CONNECTED, pdFALSE, pdFALSE, timeout_ms / portTICK_PERIOD_MS);
#     return (bits & WIFI_EVENT_CONNECTED) != 0;}""",
# )
# graph.add_node(
#     "void WifiStation::HandleScanResult()",
#     body="""void WifiStation::HandleScanResult() {
#     uint16_t ap_num = 0;
#     esp_wifi_scan_get_ap_num(&ap_num);
#     wifi_ap_record_t *ap_records = (wifi_ap_record_t *)malloc(ap_num * sizeof(wifi_ap_record_t));
#     esp_wifi_scan_get_ap_records(&ap_num, ap_records);
#     std::sort(ap_records, ap_records + ap_num, [](const wifi_ap_record_t& a, const wifi_ap_record_t& b) {
#         return a.rssi > b.rssi;});
#     auto& ssid_manager = SsidManager::GetInstance();
#     auto ssid_list = ssid_manager.GetSsidList();
#     for (int i = 0; i < ap_num; i++) {
#         auto ap_record = ap_records[i];
#         auto it = std::find_if(ssid_list.begin(), ssid_list.end(), [ap_record](const SsidItem& item) {
#             return strcmp((char *)ap_record.ssid, item.ssid.c_str()) == 0;});
#         if (it != ssid_list.end()) {
#             ESP_LOGI(TAG, "Found AP: %s, BSSID: %02x:%02x:%02x:%02x:%02x:%02x, RSSI: %d, Channel: %d, Authmode: %d",
#                 (char *)ap_record.ssid,
#                 ap_record.bssid[0], ap_record.bssid[1], ap_record.bssid[2],
#                 ap_record.bssid[3], ap_record.bssid[4], ap_record.bssid[5],
#                 ap_record.rssi, ap_record.primary, ap_record.authmode);
#             WifiApRecord record = {
#                 .ssid = it->ssid,
#                 .password = it->password,
#                 .channel = ap_record.primary,
#                 .authmode = ap_record.authmode
#             };
#             memcpy(record.bssid, ap_record.bssid, 6);
#             connect_queue_.push_back(record);
#         }
#     }
#     free(ap_records);
#     if (connect_queue_.empty()) {
#         ESP_LOGI(TAG, "Wait for next scan");
#         esp_timer_start_once(timer_handle_, 10 * 1000);
#         return;
#     }
#     StartConnect();}""",
# )

# graph.add_node(
#     "void WifiStation::StartConnect()",
#     body="""void WifiStation::StartConnect() {
#     auto ap_record = connect_queue_.front();
#     connect_queue_.erase(connect_queue_.begin());
#     ssid_ = ap_record.ssid;
#     password_ = ap_record.password;
#     if (on_connect_) {
#         on_connect_(ssid_);
#     }
#     wifi_config_t wifi_config;
#     bzero(&wifi_config, sizeof(wifi_config));
#     strcpy((char *)wifi_config.sta.ssid, ap_record.ssid.c_str());
#     strcpy((char *)wifi_config.sta.password, ap_record.password.c_str());
#     wifi_config.sta.channel = ap_record.channel;
#     memcpy(wifi_config.sta.bssid, ap_record.bssid, 6);
#     wifi_config.sta.bssid_set = true;
#     ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
#     reconnect_count_ = 0;
#     ESP_ERROR_CHECK(esp_wifi_connect());}""",
# )

# graph.add_node(
#     "int8_t WifiStation::GetRssi()",
#     body="""int8_t WifiStation::GetRssi() {
#     wifi_ap_record_t ap_info;
#     ESP_ERROR_CHECK(esp_wifi_sta_get_ap_info(&ap_info));
#     return ap_info.rssi;}""",
# )

# graph.add_node(
#     "uint8_t WifiStation::GetChannel()",
#     body="""uint8_t WifiStation::GetChannel() {
#     wifi_ap_record_t ap_info;
#     ESP_ERROR_CHECK(esp_wifi_sta_get_ap_info(&ap_info));
#     return ap_info.primary;}""",
# )

# graph.add_node(
#     "bool WifiStation::IsConnected()",
#     body="""bool WifiStation::IsConnected() {
#     return xEventGroupGetBits(event_group_) & WIFI_EVENT_CONNECTED;}""",
# )

# graph.add_node(
#     "void WifiStation::SetPowerSaveMode(bool enabled)",
#     body="""void WifiStation::SetPowerSaveMode(bool enabled) {
#     ESP_ERROR_CHECK(esp_wifi_set_ps(enabled ? WIFI_PS_MIN_MODEM : WIFI_PS_NONE));}""",
# )

# graph.add_node(
#     "void WifiStation::WifiEventHandler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data)",
#     body="""void WifiStation::WifiEventHandler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data) {
#     auto* this_ = static_cast<WifiStation*>(arg);
#     if (event_id == WIFI_EVENT_STA_START) {
#         esp_wifi_scan_start(nullptr, false);
#         if (this_->on_scan_begin_) {
#             this_->on_scan_begin_();
#         }
#     } else if (event_id == WIFI_EVENT_SCAN_DONE) {
#         this_->HandleScanResult();
#     } else if (event_id == WIFI_EVENT_STA_DISCONNECTED) {
#         xEventGroupClearBits(this_->event_group_, WIFI_EVENT_CONNECTED);
#         if (this_->reconnect_count_ < MAX_RECONNECT_COUNT) {
#             ESP_ERROR_CHECK(esp_wifi_connect());
#             this_->reconnect_count_++;
#             ESP_LOGI(TAG, "Reconnecting %s (attempt %d / %d)", this_->ssid_.c_str(), this_->reconnect_count_, MAX_RECONNECT_COUNT);
#             return;
#         }
#         if (!this_->connect_queue_.empty()) {
#             this_->StartConnect();
#             return;
#         }
#         ESP_LOGI(TAG, "No more AP to connect, wait for next scan");
#         esp_timer_start_once(this_->timer_handle_, 10 * 1000);
#     } else if (event_id == WIFI_EVENT_STA_CONNECTED) {
#     }}""",
# )

# graph.add_node(
#     "void WifiStation::IpEventHandler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data)",
#     body="""void WifiStation::IpEventHandler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data) {
#     auto* this_ = static_cast<WifiStation*>(arg);
#     auto* event = static_cast<ip_event_got_ip_t*>(event_data);
#     char ip_address[16];
#     esp_ip4addr_ntoa(&event->ip_info.ip, ip_address, sizeof(ip_address));
#     this_->ip_address_ = ip_address;
#     ESP_LOGI(TAG, "Got IP: %s", this_->ip_address_.c_str());
#     xEventGroupSetBits(this_->event_group_, WIFI_EVENT_CONNECTED);
#     if (this_->on_connected_) {
#         this_->on_connected_(this_->ssid_);
#     }
#     this_->connect_queue_.clear();
#     this_->reconnect_count_ = 0;}""",
# )

# 添加代码之间的调用和引用关系的边
# HandleScanResult调用StartConnect
# graph.add_edge("WifiStation& WifiStation::GetInstance()", "class WifiStation")
# graph.add_edge("WifiStation::WifiStation()", "class WifiStation")
# graph.add_edge("WifiStation::~WifiStation()", "class WifiStation")
# graph.add_edge(
#     "void WifiStation::AddAuth(const std::string &&ssid, const std::string &&password)",
#     "class WifiStation",
# )
# graph.add_edge(
#     "void WifiStation::Stop()",
#     "class WifiStation",
# )
# graph.add_edge(
#     "void WifiStation::OnScanBegin(std::function<void()> on_scan_begin)",
#     "class WifiStation",
# )
# graph.add_edge(
#     "void WifiStation::OnConnect(std::function<void(const std::string& ssid)> on_connect)",
#     "class WifiStation",
# )
# graph.add_edge(
#     "void WifiStation::OnConnected(std::function<void(const std::string& ssid)> on_connected)",
#     "class WifiStation",
# )
# graph.add_edge("void WifiStation::Start()", "class WifiStation")
# graph.add_edge(
#     "void WifiStation::Start()",
#     "void WifiStation::WifiEventHandler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data)",
# )
# graph.add_edge(
#     "void WifiStation::Start()",
#     "void WifiStation::IpEventHandler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data)",
# )
# # graph.add_edge(
# #     "bool WifiStation::WaitForConnected(int timeout_ms)", "class WifiStation"
# # )
# # graph.add_edge("void WifiStation::HandleScanResult()", "class WifiStation")
# graph.add_edge("void WifiStation::HandleScanResult()", "struct WifiApRecord")
# graph.add_edge("struct WifiApRecord", "void WifiStation::StartConnect()")
# graph.add_edge(
#     "void WifiStation::HandleScanResult()",
#     "void WifiStation::StartConnect()",
# )
# # graph.add_edge("void WifiStation::StartConnect()", "class WifiStation")
# # graph.add_edge("int8_t WifiStation::GetRssi()", "class WifiStation")
# # graph.add_edge("uint8_t WifiStation::GetChannel()", "class WifiStation")
# # graph.add_edge("bool WifiStation::IsConnected()", "class WifiStation")
# # graph.add_edge("void WifiStation::SetPowerSaveMode(bool enabled)", "class WifiStation")
# # graph.add_edge(
# #     "void WifiStation::WifiEventHandler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data)",
# #     "class WifiStation",
# # )
# graph.add_edge(
#     "void WifiStation::WifiEventHandler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data)",
#     "void WifiStation::HandleScanResult()",
# )
# graph.add_edge(
#     "void WifiStation::WifiEventHandler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data)",
#     "void WifiStation::StartConnect()",
# )

# graph.add_edge(
#     "void WifiStation::IpEventHandler(void* arg, esp_event_base_t event_base, int32_t event_id, void* event_data)",
#     "class WifiStation",
# )

# 打印所有节点名称和所有的边
for node in graph.nodes:
    print("节点:", node)
for edge in graph.edges:
    print("边:", edge)


# 打印出这个树结构
def print_graph(graph, node, level=0):
    print("  " * level + node)
    for child in graph.successors(node):
        print_graph(graph, child, level + 1)


print("Graph structure:")
for root in graph.nodes:
    if graph.in_degree(root) == 0:  # 找到根节点
        print_graph(graph, root)


# 帮我写一个遍历图的流程，深度优先后序遍历
def dfs_post_order(graph, node, visited=None, callback=None):
    if visited is None:
        visited = set()
    visited.add(node)
    for neighbor in graph.successors(node):
        if neighbor not in visited:
            dfs_post_order(graph, neighbor, visited, callback=callback)
    # print(node)
    if callback:
        callback(node)


# 帮我写一个遍历图的流程，深度优先前序遍历
def dfs_pre_order(graph, node, visited=None, callback=None):
    if visited is None:
        visited = set()
    # print(node)
    if callback:
        callback(node)
    visited.add(node)
    for neighbor in graph.successors(node):
        if neighbor not in visited:
            dfs_pre_order(graph, neighbor, visited, callback=callback)


# 获取当前节点的所有入边的节点
def get_incoming_nodes(graph, node):
    return list(graph.predecessors(node))


# 获取当前节点的所有出边的节点
def get_outgoing_nodes(graph, node):
    return list(graph.successors(node))


# 使用深度优先后序遍历打印图
print("\nDFS Post-order Traversal:")
visited_nodes = set()
for root in graph.nodes:
    if graph.in_degree(root) == 0:  # 找到根节点
        dfs_post_order(graph, root, visited_nodes)

# 使用深度优先前序遍历打印图
print("\nDFS Pre-order Traversal:")
visited_nodes = set()
for root in graph.nodes:
    if graph.in_degree(root) == 0:  # 找到根节点
        dfs_pre_order(graph, root, visited_nodes)
from pydantic import BaseModel, Field
from typing import List, Optional
# 配置选项
DEFAULT_MAX_ATTEMPTS = 3  # 默认最大尝试次数
# 新增知识块数据结构
class KnowledgeItem(BaseModel):
    question: str = Field(description="待验证的问题")
    evidence: Optional[str] = Field(description="验证过程中收集的证据")
    conclusion: Optional[str] = Field(description="验证结论")
    causal_chain_closed: bool = Field(default=False, description="是否已形成闭环")
    validation_attempts: int = Field(default=0, description="验证尝试次数")
    is_suspended: bool = Field(default=False, description="是否为搁置状态")
    max_attempts: int = Field(default=DEFAULT_MAX_ATTEMPTS, description="最大尝试次数")

class Evidence(BaseModel):
    valid: bool = Field(description="证据是否有效")
    content: str = Field(description="证据内容")
    source: str = Field(description="证据来源节点") # 用逗号分隔的节点名称

# 修改图节点结构，为每个节点添加知识块属性
for node in graph.nodes:
    graph.nodes[node]["knowledge_blocks"] = []
    graph.nodes[node]["documentation"] = ""
    graph.nodes[node]["documentation_generated"] = False
    graph.nodes[node]["validated_causal_chains"] = []