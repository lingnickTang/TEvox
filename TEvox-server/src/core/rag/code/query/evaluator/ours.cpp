# 复用底层功能模块
"Implement a smart reminder system that execute reminders with persistent storage, precise timing, and interactive notifications."

#include <vector>
#include <string>
#include <memory>
#include <functional>
#include "esp_timer.h"
#include "nvs_flash.h"
#include "esp_log.h"

// Forward declarations for interfaces
class ITimerService;
class IStorageService;
class ILoggingService;

// Reminder structure
struct Reminder {
    uint64_t id;
    std::string message;
    uint64_t timestamp; // Unix timestamp
    bool active;
    
    Reminder(uint64_t id, const std::string& msg, uint64_t ts) 
        : id(id), message(msg), timestamp(ts), active(true) {}
};

// Interface for timer service
class ITimerService {
public:
    virtual ~ITimerService() = default;
    virtual esp_err_t Create(const esp_timer_create_args_t* args, esp_timer_handle_t* out_handle) = 0;
    virtual esp_err_t StartOnce(esp_timer_handle_t handle, uint64_t timeout_us) = 0;
    virtual esp_err_t Stop(esp_timer_handle_t handle) = 0;
    virtual esp_err_t Delete(esp_timer_handle_t handle) = 0;
};

// Interface for storage service
class IStorageService {
public:
    virtual ~IStorageService() = default;
    virtual void SaveReminders(const std::vector<Reminder>& reminders) = 0;
    virtual void LoadReminders(std::vector<Reminder>& reminders) = 0;
};

// Interface for logging service
class ILoggingService {
public:
    virtual ~ILoggingService() = default;
    virtual void LogInfo(const char* tag, const char* message) = 0;
    virtual void LogError(const char* tag, const char* message) = 0;
};

// Timer service implementation using ESP-IDF timers
class TimerServiceImpl : public ITimerService {
public:
    esp_err_t Create(const esp_timer_create_args_t* args, esp_timer_handle_t* out_handle) override {
        return esp_timer_create(args, out_handle);
    }
    
    esp_err_t StartOnce(esp_timer_handle_t handle, uint64_t timeout_us) override {
        return esp_timer_start_once(handle, timeout_us);
    }
    
    esp_err_t Stop(esp_timer_handle_t handle) override {
        return esp_timer_stop(handle);
    }
    
    esp_err_t Delete(esp_timer_handle_t handle) override {
        return esp_timer_delete(handle);
    }
};

// Storage service implementation using NVS
class NvsStorageService : public IStorageService {
private:
    static constexpr const char* TAG = "NvsStorage";
    static constexpr const char* NVS_NAMESPACE = "reminders";
    static constexpr const char* REMINDERS_KEY = "reminders";

public:
    void SaveReminders(const std::vector<Reminder>& reminders) override {
        nvs_handle_t nvs_handle;
        esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &nvs_handle);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "Failed to open NVS: %s", esp_err_to_name(err));
            return;
        }

        // Serialize reminders to binary data (simplified approach)
        // In practice, you might want to serialize to JSON or another format
        size_t data_size = reminders.size() * sizeof(Reminder);
        std::vector<uint8_t> data(data_size);
        
        if (!data.empty()) {
            memcpy(data.data(), reminders.data(), data_size);
            err = nvs_set_blob(nvs_handle, REMINDERS_KEY, data.data(), data_size);
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "Failed to save reminders: %s", esp_err_to_name(err));
            } else {
                nvs_commit(nvs_handle);
            }
        }
        
        nvs_close(nvs_handle);
    }

    void LoadReminders(std::vector<Reminder>& reminders) override {
        nvs_handle_t nvs_handle;
        esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs_handle);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "NVS namespace %s doesn't exist", NVS_NAMESPACE);
            return;
        }

        size_t required_size = 0;
        err = nvs_get_blob(nvs_handle, REMINDERS_KEY, nullptr, &required_size);
        if (err != ESP_OK || required_size == 0) {
            nvs_close(nvs_handle);
            return;
        }

        std::vector<uint8_t> data(required_size);
        err = nvs_get_blob(nvs_handle, REMINDERS_KEY, data.data(), &required_size);
        if (err == ESP_OK && !data.empty()) {
            // Deserialize reminders from blob data
            size_t reminder_count = required_size / sizeof(Reminder);
            reminders.resize(reminder_count);
            memcpy(reminders.data(), data.data(), required_size);
        }
        
        nvs_close(nvs_handle);
    }
};

// Logging module implementation
class LoggingModule : public ILoggingService {
public:
    void LogInfo(const char* tag, const char* message) override {
        ESP_LOGI(tag, "%s", message);
    }
    
    void LogError(const char* tag, const char* message) override {
        ESP_LOGE(tag, "%s", message);
    }
};

// Smart reminder manager
class SmartReminderManager {
private:
    ITimerService& timer_service_;
    IStorageService& storage_service_;
    ILoggingService& logging_service_;
    std::vector<Reminder> reminders_;
    std::vector<esp_timer_handle_t> timer_handles_;
    static constexpr const char* TAG = "SmartReminder";
    
    // Callback function for timer expiration
    static void TimerCallback(void* arg) {
        SmartReminderManager* manager = static_cast<SmartReminderManager*>(arg);
        manager->ExecuteReminder();
    }

public:
    SmartReminderManager(ITimerService& timer_service,
                        IStorageService& storage_service,
                        ILoggingService& logging_service)
        : timer_service_(timer_service),
          storage_service_(storage_service),
          logging_service_(logging_service) {
        // Load existing reminders from persistent storage
        LoadReminders();
    }

    ~SmartReminderManager() {
        // Clean up timers
        for (auto handle : timer_handles_) {
            timer_service_.Delete(handle);
        }
    }

    // Add a new reminder
    uint64_t AddReminder(const std::string& message, uint64_t timestamp) {
        uint64_t id = GetNextId();
        Reminder reminder(id, message, timestamp);
        reminders_.push_back(reminder);
        ScheduleReminder(reminder);
        SaveReminders();
        logging_service_.LogInfo(TAG, "Added reminder");
        return id;
    }

    // Remove a reminder by ID
    bool RemoveReminder(uint64_t id) {
        for (auto it = reminders_.begin(); it != reminders_.end(); ++it) {
            if (it->id == id) {
                // Stop and delete timer if exists
                if (it - reminders_.begin() < timer_handles_.size()) {
                    timer_service_.Stop(timer_handles_[it - reminders_.begin()]);
                    timer_service_.Delete(timer_handles_[it - reminders_.begin()]);
                }
                reminders_.erase(it);
                SaveReminders();
                logging_service_.LogInfo(TAG, "Removed reminder");
                return true;
            }
        }
        return false;
    }

    // Update a reminder's timestamp
    bool UpdateReminderTimestamp(uint64_t id, uint64_t new_timestamp) {
        for (auto& reminder : reminders_) {
            if (reminder.id == id) {
                reminder.timestamp = new_timestamp;
                // Reschedule the reminder
                ScheduleReminder(reminder);
                SaveReminders();
                logging_service_.LogInfo(TAG, "Updated reminder timestamp");
                return true;
            }
        }
        return false;
    }

    // Execute a reminder notification
    void ExecuteReminder() {
        // This would be called when a timer expires
        // For simplicity, we'll just log the event
        logging_service_.LogInfo(TAG, "Executing reminder notification");
        // In a real implementation, this would trigger UI notifications
        // or send alerts through various channels
    }

private:
    uint64_t GetNextId() {
        if (reminders_.empty()) return 1;
        uint64_t max_id = 0;
        for (const auto& reminder : reminders_) {
            if (reminder.id > max_id) max_id = reminder.id;
        }
        return max_id + 1;
    }

    void ScheduleReminder(const Reminder& reminder) {
        // Calculate delay in microseconds
        uint64_t current_time = esp_timer_get_time();
        uint64_t delay_us = (reminder.timestamp - current_time / 1000000) * 1000000;
        
        // Ensure non-negative delay
        if (delay_us > 0) {
            esp_timer_create_args_t timer_args = {
                .callback = &TimerCallback,
                .arg = this,
                .name = "reminder_timer",
                .skip_unhandled_events = false
            };
            
            esp_timer_handle_t timer_handle;
            esp_err_t err = timer_service_.Create(&timer_args, &timer_handle);
            if (err == ESP_OK) {
                timer_handles_.push_back(timer_handle);
                timer_service_.StartOnce(timer_handle, delay_us);
                logging_service_.LogInfo(TAG, "Scheduled reminder");
            } else {
                logging_service_.LogError(TAG, "Failed to create timer");
            }
        }
    }

    void LoadReminders() {
        reminders_.clear();
        storage_service_.LoadReminders(reminders_);
        logging_service_.LogInfo(TAG, "Loaded reminders from storage");
        
        // Schedule all loaded reminders
        for (const auto& reminder : reminders_) {
            if (reminder.active) {
                ScheduleReminder(reminder);
            }
        }
    }

    void SaveReminders() {
        storage_service_.SaveReminders(reminders_);
        logging_service_.LogInfo(TAG, "Saved reminders to storage");
    }
};