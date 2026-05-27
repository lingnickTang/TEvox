#include <esp_log.h>
#include <nvs.h>
#include <time.h>
#include <vector>
#include <string>
#include <queue>
#include <algorithm>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/timers.h>

#define TAG "SmartReminder"
#define REMINDERS_NVS_NAMESPACE "reminders"
#define MAX_REMINDERS 100
#define REMINDER_KEY_PREFIX "reminder_"

struct Reminder {
    uint32_t id;
    std::string message;
    time_t trigger_time;
    bool active;
    bool repeated;
    uint32_t repeat_interval; // in seconds
};

class ReminderManager {
private:
    std::vector<Reminder> reminders_;
    uint32_t next_id_;
    
    static ReminderManager* instance_;
    
    ReminderManager() : next_id_(1) {
        LoadRemindersFromNVS();
    }
    
public:
    static ReminderManager& GetInstance() {
        if (instance_ == nullptr) {
            instance_ = new ReminderManager();
        }
        return *instance_;
    }
    
    uint32_t AddReminder(const std::string& message, time_t trigger_time, bool repeated = false, uint32_t repeat_interval = 0) {
        Reminder reminder;
        reminder.id = next_id_++;
        reminder.message = message;
        reminder.trigger_time = trigger_time;
        reminder.active = true;
        reminder.repeated = repeated;
        reminder.repeat_interval = repeat_interval;
        
        reminders_.push_back(reminder);
        SaveRemindersToNVS();
        
        ESP_LOGI(TAG, "Added reminder ID %u for %s", reminder.id, ctime(&trigger_time));
        return reminder.id;
    }
    
    bool CancelReminder(uint32_t id) {
        auto it = std::find_if(reminders_.begin(), reminders_.end(),
                              [id](const Reminder& r) { return r.id == id; });
        if (it != reminders_.end()) {
            it->active = false;
            SaveRemindersToNVS();
            ESP_LOGI(TAG, "Cancelled reminder ID %u", id);
            return true;
        }
        return false;
    }
    
    void ProcessReminders() {
        time_t current_time = time(nullptr);
        std::vector<uint32_t> completed_reminders;
        
        for (auto& reminder : reminders_) {
            if (reminder.active && reminder.trigger_time <= current_time) {
                ExecuteReminder(reminder);
                
                if (reminder.repeated) {
                    reminder.trigger_time += reminder.repeat_interval;
                    ESP_LOGI(TAG, "Repeating reminder ID %u for %s", 
                            reminder.id, ctime(&reminder.trigger_time));
                } else {
                    reminder.active = false;
                    completed_reminders.push_back(reminder.id);
                }
            }
        }
        
        // Remove completed non-repeating reminders
        reminders_.erase(
            std::remove_if(reminders_.begin(), reminders_.end(),
                          [&completed_reminders](const Reminder& r) {
                              return std::find(completed_reminders.begin(), 
                                             completed_reminders.end(), r.id) != 
                                     completed_reminders.end();
                          }),
            reminders_.end());
        
        SaveRemindersToNVS();
    }
    
    void ExecuteReminder(const Reminder& reminder) {
        ESP_LOGI(TAG, "Executing reminder: %s", reminder.message.c_str());
        
        // This would be replaced with actual notification implementation
        // For example: display on screen, play sound, send notification, etc.
        NotifyUser(reminder.message);
    }
    
    void NotifyUser(const std::string& message) {
        // Placeholder for notification logic
        // Could implement OLED display, buzzer, HTTP notification, etc.
        ESP_LOGI(TAG, "NOTIFICATION: %s", message.c_str());
    }
    
private:
    void SaveRemindersToNVS() {
        nvs_handle_t nvs_handle;
        esp_err_t err = nvs_open(REMINDERS_NVS_NAMESPACE, NVS_READWRITE, &nvs_handle);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to open NVS: %s", esp_err_to_name(err));
            return;
        }
        
        // Store number of reminders
        err = nvs_set_u32(nvs_handle, "count", reminders_.size());
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to store reminder count: %s", esp_err_to_name(err));
        }
        
        // Store each reminder
        for (size_t i = 0; i < reminders_.size(); ++i) {
            const Reminder& reminder = reminders_[i];
            
            std::string id_key = REMINDER_KEY_PREFIX + std::to_string(i) + "_id";
            std::string msg_key = REMINDER_KEY_PREFIX + std::to_string(i) + "_msg";
            std::string time_key = REMINDER_KEY_PREFIX + std::to_string(i) + "_time";
            std::string active_key = REMINDER_KEY_PREFIX + std::to_string(i) + "_active";
            std::string repeated_key = REMINDER_KEY_PREFIX + std::to_string(i) + "_repeated";
            std::string interval_key = REMINDER_KEY_PREFIX + std::to_string(i) + "_interval";
            
            err = nvs_set_u32(nvs_handle, id_key.c_str(), reminder.id);
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "Failed to store reminder ID: %s", esp_err_to_name(err));
            }
            
            err = nvs_set_str(nvs_handle, msg_key.c_str(), reminder.message.c_str());
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "Failed to store reminder message: %s", esp_err_to_name(err));
            }
            
            err = nvs_set_u32(nvs_handle, time_key.c_str(), static_cast<uint32_t>(reminder.trigger_time));
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "Failed to store reminder time: %s", esp_err_to_name(err));
            }
            
            err = nvs_set_u8(nvs_handle, active_key.c_str(), reminder.active ? 1 : 0);
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "Failed to store reminder active status: %s", esp_err_to_name(err));
            }
            
            err = nvs_set_u8(nvs_handle, repeated_key.c_str(), reminder.repeated ? 1 : 0);
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "Failed to store reminder repeat status: %s", esp_err_to_name(err));
            }
            
            err = nvs_set_u32(nvs_handle, interval_key.c_str(), reminder.repeat_interval);
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "Failed to store reminder interval: %s", esp_err_to_name(err));
            }
        }
        
        err = nvs_commit(nvs_handle);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to commit NVS changes: %s", esp_err_to_name(err));
        }
        
        nvs_close(nvs_handle);
    }
    
    void LoadRemindersFromNVS() {
        nvs_handle_t nvs_handle;
        esp_err_t err = nvs_open(REMINDERS_NVS_NAMESPACE, NVS_READONLY, &nvs_handle);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "Failed to open NVS for loading reminders: %s", esp_err_to_name(err));
            return;
        }
        
        uint32_t count;
        err = nvs_get_u32(nvs_handle, "count", &count);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "No reminders found in NVS");
            nvs_close(nvs_handle);
            return;
        }
        
        reminders_.clear();
        for (uint32_t i = 0; i < count && i < MAX_REMINDERS; ++i) {
            Reminder reminder;
            
            std::string id_key = REMINDER_KEY_PREFIX + std::to_string(i) + "_id";
            std::string msg_key = REMINDER_KEY_PREFIX + std::to_string(i) + "_msg";
            std::string time_key = REMINDER_KEY_PREFIX + std::to_string(i) + "_time";
            std::string active_key = REMINDER_KEY_PREFIX + std::to_string(i) + "_active";
            std::string repeated_key = REMINDER_KEY_PREFIX + std::to_string(i) + "_repeated";
            std::string interval_key = REMINDER_KEY_PREFIX + std::to_string(i) + "_interval";
            
            err = nvs_get_u32(nvs_handle, id_key.c_str(), &reminder.id);
            if (err != ESP_OK) continue;
            
            char msg_buf[256];
            size_t msg_len = sizeof(msg_buf);
            err = nvs_get_str(nvs_handle, msg_key.c_str(), msg_buf, &msg_len);
            if (err == ESP_OK) {
                reminder.message = std::string(msg_buf);
            } else {
                continue;
            }
            
            uint32_t time_val;
            err = nvs_get_u32(nvs_handle, time_key.c_str(), &time_val);
            if (err == ESP_OK) {
                reminder.trigger_time = static_cast<time_t>(time_val);
            } else {
                continue;
            }
            
            uint8_t active_val;
            err = nvs_get_u8(nvs_handle, active_key.c_str(), &active_val);
            if (err == ESP_OK) {
                reminder.active = (active_val != 0);
            } else {
                reminder.active = true;
            }
            
            uint8_t repeated_val;
            err = nvs_get_u8(nvs_handle, repeated_key.c_str(), &repeated_val);
            if (err == ESP_OK) {
                reminder.repeated = (repeated_val != 0);
            } else {
                reminder.repeated = false;
            }
            
            uint32_t interval_val;
            err = nvs_get_u32(nvs_handle, interval_key.c_str(), &interval_val);
            if (err == ESP_OK) {
                reminder.repeat_interval = interval_val;
            } else {
                reminder.repeat_interval = 0;
            }
            
            reminders_.push_back(reminder);
            if (reminder.id >= next_id_) {
                next_id_ = reminder.id + 1;
            }
        }
        
        nvs_close(nvs_handle);
        ESP_LOGI(TAG, "Loaded %zu reminders from NVS", reminders_.size());
    }
    
    // Static pointer for singleton instance
    static ReminderManager* instance_;
};

// Initialize static member
ReminderManager* ReminderManager::instance_ = nullptr;

// Example usage task
extern "C" void reminder_task(void* pvParameters) {
    ReminderManager& rm = ReminderManager::GetInstance();
    
    while (1) {
        rm.ProcessReminders();
        vTaskDelay(pdMS_TO_TICKS(1000)); // Check every second
    }
}

// Public API functions
extern "C" uint32_t reminder_add(const char* message, time_t trigger_time, bool repeated, uint32_t repeat_interval) {
    return ReminderManager::GetInstance().AddReminder(message, trigger_time, repeated, repeat_interval);
}

extern "C" bool reminder_cancel(uint32_t id) {
    return ReminderManager::GetInstance().CancelReminder(id);
}

extern "C" void reminder_start_task() {
    xTaskCreate(reminder_task, "reminder_task", 4096, NULL, 5, NULL);
}