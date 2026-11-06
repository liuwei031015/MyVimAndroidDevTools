package dev.example.devicename;

import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.lifecycle.ViewModelProvider;

public class MainActivity extends ComponentActivity {
    private DeviceNameViewModel viewModel;
    private EditText nameInput;
    private TextView currentName;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        nameInput = findViewById(R.id.device_name_input);
        currentName = findViewById(R.id.current_device_name);
        Button saveButton = findViewById(R.id.save_device_name);
        viewModel = new ViewModelProvider(this).get(DeviceNameViewModel.class);

        viewModel.getName().observe(this, name -> {
            currentName.setText(getString(R.string.current_device_name, name));
            if (!nameInput.hasFocus()) {
                nameInput.setText(name);
            }
        });
        saveButton.setOnClickListener(view -> {
            if (!viewModel.saveName(nameInput.getText().toString())) {
                nameInput.setError(getString(R.string.device_name_required));
            }
        });
    }
}
