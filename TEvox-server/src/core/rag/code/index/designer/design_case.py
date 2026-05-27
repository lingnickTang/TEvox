what_case_0 = """
SsidManager::SsidManager() {
    LoadFromNvs();
}

SsidManager::~SsidManager() {
}

void SsidManager::Clear() {
    ssid_list_.clear();
    SaveToNvs();
}

void SsidManager::LoadFromNvs() {
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
    for (int i = 0; i < MAX_WIFI_SSID_COUNT; i++) {
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
}

void SsidManager::SaveToNvs() {
    nvs_handle_t nvs_handle;
    ESP_ERROR_CHECK(nvs_open(NVS_NAMESPACE, NVS_READWRITE, &nvs_handle));
    for (int i = 0; i < MAX_WIFI_SSID_COUNT; i++) {
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
}

void SsidManager::AddSsid(const std::string& ssid, const std::string& password) {
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
}

void SsidManager::RemoveSsid(int index) {
    if (index < 0 || index >= ssid_list_.size()) {
        ESP_LOGW(TAG, "Invalid index %d", index);
        return;
    }
    ssid_list_.erase(ssid_list_.begin() + index);
    SaveToNvs();
}

void SsidManager::SetDefaultSsid(int index) {
    if (index < 0 || index >= ssid_list_.size()) {
        ESP_LOGW(TAG, "Invalid index %d", index);
        return;
    }
    // Move the ssid at index to the front of the list
    auto item = ssid_list_[index];
    ssid_list_.erase(ssid_list_.begin() + index);
    ssid_list_.insert(ssid_list_.begin(), item);
    SaveToNvs();
}
"""

what_case_1 = """
Settings::Settings(const std::string& ns, bool read_write) : ns_(ns), read_write_(read_write) {
    nvs_open(ns.c_str(), read_write_ ? NVS_READWRITE : NVS_READONLY, &nvs_handle_);
}

Settings::~Settings() {
    if (nvs_handle_ != 0) {
        if (read_write_ && dirty_) {
            ESP_ERROR_CHECK(nvs_commit(nvs_handle_));
        }
        nvs_close(nvs_handle_);
    }
}

std::string Settings::GetString(const std::string& key, const std::string& default_value) {
    if (nvs_handle_ == 0) {
        return default_value;
    }

    size_t length = 0;
    if (nvs_get_str(nvs_handle_, key.c_str(), nullptr, &length) != ESP_OK) {
        return default_value;
    }

    std::string value;
    value.resize(length);
    ESP_ERROR_CHECK(nvs_get_str(nvs_handle_, key.c_str(), value.data(), &length));
    while (!value.empty() && value.back() == '\0') {
        value.pop_back();
    }
    return value;
}

void Settings::SetString(const std::string& key, const std::string& value) {
    if (read_write_) {
        ESP_ERROR_CHECK(nvs_set_str(nvs_handle_, key.c_str(), value.c_str()));
        dirty_ = true;
    } else {
        ESP_LOGW(TAG, "Namespace %s is not open for writing", ns_.c_str());
    }
}

int32_t Settings::GetInt(const std::string& key, int32_t default_value) {
    if (nvs_handle_ == 0) {
        return default_value;
    }

    int32_t value;
    if (nvs_get_i32(nvs_handle_, key.c_str(), &value) != ESP_OK) {
        return default_value;
    }
    return value;
}

void Settings::SetInt(const std::string& key, int32_t value) {
    if (read_write_) {
        ESP_ERROR_CHECK(nvs_set_i32(nvs_handle_, key.c_str(), value));
        dirty_ = true;
    } else {
        ESP_LOGW(TAG, "Namespace %s is not open for writing", ns_.c_str());
    }
}

void Settings::EraseKey(const std::string& key) {
    if (read_write_) {
        auto ret = nvs_erase_key(nvs_handle_, key.c_str());
        if (ret != ESP_ERR_NVS_NOT_FOUND) {
            ESP_ERROR_CHECK(ret);
        }
    } else {
        ESP_LOGW(TAG, "Namespace %s is not open for writing", ns_.c_str());
    }
}

void Settings::EraseAll() {
    if (read_write_) {
        ESP_ERROR_CHECK(nvs_erase_all(nvs_handle_));
    } else {
        ESP_LOGW(TAG, "Namespace %s is not open for writing", ns_.c_str());
    }
}

"""

what_case_2 = """

"""
what_case_3 = """
#include "dns_server.h"
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <esp_log.h>
#include <lwip/sockets.h>
#include <lwip/netdb.h>

#define TAG "DnsServer"

DnsServer::DnsServer() {
}

DnsServer::~DnsServer() {
}

void DnsServer::Start(esp_ip4_addr_t gateway) {
    ESP_LOGI(TAG, "Starting DNS server");
    gateway_ = gateway;

    fd_ = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (fd_ < 0) {
        ESP_LOGE(TAG, "Failed to create socket");
        return;
    }

    struct sockaddr_in server_addr;
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = htonl(INADDR_ANY);
    server_addr.sin_port = htons(port_);

    if (bind(fd_, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        ESP_LOGE(TAG, "failed to bind port %d", port_);
        close(fd_);
        return;
    }

    xTaskCreate([](void* arg) {
        DnsServer* dns_server = static_cast<DnsServer*>(arg);
        dns_server->Run();
    }, "DnsServerTask", 4096, this, 5, NULL);
}

void DnsServer::Stop() {
    ESP_LOGI(TAG, "Stopping DNS server");
}

void DnsServer::Run() {
    char buffer[512];
    while (1) {
        struct sockaddr_in client_addr;
        socklen_t client_addr_len = sizeof(client_addr);
        int len = recvfrom(fd_, buffer, sizeof(buffer), 0, (struct sockaddr *)&client_addr, &client_addr_len);
        if (len < 0) {
            ESP_LOGE(TAG, "recvfrom failed, errno=%d", errno);
            continue;
        }

        // Simple DNS response: point all queries to 192.168.4.1
        buffer[2] |= 0x80;  // Set response flag
        buffer[3] |= 0x80;  // Set Recursion Available
        buffer[7] = 1;      // Set answer count to 1

        // Add answer section
        memcpy(&buffer[len], "\xc0\x0c", 2);  // Name pointer
        len += 2;
        memcpy(&buffer[len], "\x00\x01\x00\x01\x00\x00\x00\x1c\x00\x04", 10);  // Type, class, TTL, data length
        len += 10;
        memcpy(&buffer[len], &gateway_.addr, 4);  // 192.168.4.1
        len += 4;
        ESP_LOGI(TAG, "Sending DNS response to %s", inet_ntoa(gateway_.addr));

        sendto(fd_, buffer, len, 0, (struct sockaddr *)&client_addr, client_addr_len);
    }
}
"""