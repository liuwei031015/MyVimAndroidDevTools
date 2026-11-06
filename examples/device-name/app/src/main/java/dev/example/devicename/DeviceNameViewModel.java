package dev.example.devicename;

import android.app.Application;
import android.content.SharedPreferences;

import androidx.lifecycle.AndroidViewModel;
import androidx.lifecycle.LiveData;
import androidx.lifecycle.MutableLiveData;

public class DeviceNameViewModel extends AndroidViewModel {
    private static final String PREFS = "device_settings";
    private static final String NAME = "device_name";

    private final SharedPreferences preferences;
    private final MutableLiveData<String> name = new MutableLiveData<>();

    public DeviceNameViewModel(Application application) {
        super(application);
        preferences = application.getSharedPreferences(PREFS, Application.MODE_PRIVATE);
        name.setValue(preferences.getString(NAME, application.getString(R.string.default_device_name)));
    }

    public LiveData<String> getName() {
        return name;
    }

    public boolean saveName(String value) {
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            return false;
        }
        preferences.edit().putString(NAME, normalized).apply();
        name.setValue(normalized);
        return true;
    }
}
