package com.girrig97.waterlogger;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.text.SimpleDateFormat;
import java.util.UUID;

public class MainActivity extends Activity {
    private static final UUID SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");

    private BluetoothAdapter bluetoothAdapter;
    private final List<BluetoothDevice> pairedDevices = new ArrayList<>();
    private BluetoothDevice selectedDevice;
    private TextView statusText;
    private TextView recordsText;
    private Spinner deviceSpinner;
    private Button connectButton;
    private Button disconnectButton;
    private BluetoothSocket socket;
    private BufferedReader reader;
    private OutputStream writer;
    private volatile boolean liveMode = false;
    private Thread liveThread;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        bluetoothAdapter = BluetoothAdapter.getDefaultAdapter();
        buildUi();
        requestBluetoothPermission();
        loadPairedDevices();
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(28, 28, 28, 28);

        TextView title = new TextView(this);
        title.setText("Water Logger Companion");
        title.setTextSize(24);
        title.setPadding(0, 0, 0, 18);
        root.addView(title);

        deviceSpinner = new Spinner(this);
        root.addView(deviceSpinner);

        connectButton = button("Connect");
        disconnectButton = button("Disconnect");
        disconnectButton.setEnabled(false);
        root.addView(connectButton);
        root.addView(disconnectButton);

        addActionButtons(root);

        statusText = new TextView(this);
        statusText.setText("Select a paired Orange Pi Bluetooth device, then connect.");
        statusText.setTextSize(15);
        statusText.setPadding(0, 18, 0, 18);
        root.addView(statusText);

        recordsText = new TextView(this);
        recordsText.setTextSize(14);
        recordsText.setTextIsSelectable(true);

        ScrollView scrollView = new ScrollView(this);
        scrollView.addView(recordsText);
        root.addView(scrollView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                0,
                1
        ));

        setContentView(root);

        connectButton.setOnClickListener(v -> runInBackground(this::connect));
        disconnectButton.setOnClickListener(v -> disconnect());

        deviceSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                if (position >= 0 && position < pairedDevices.size()) {
                    selectedDevice = pairedDevices.get(position);
                }
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
                selectedDevice = null;
            }
        });
    }

    private void addActionButtons(LinearLayout root) {
        Button status = button("System Status");
        Button summary = button("Record Count");
        Button times = button("List Record Times");
        Button latest = button("Latest Reading");
        Button live = button("Start Live Readings");
        Button stopLive = button("Stop Live Readings");
        Button syncTime = button("Sync Time + Log");
        Button log = button("Log Fresh Reading");
        Button download = button("Download Latest Week");
        Button downloadAll = button("Download All Weeks");
        Button resume = button("Resume Normal Logging");

        root.addView(status);
        root.addView(summary);
        root.addView(times);
        root.addView(latest);
        root.addView(live);
        root.addView(stopLive);
        root.addView(syncTime);
        root.addView(log);
        root.addView(download);
        root.addView(downloadAll);
        root.addView(resume);

        status.setOnClickListener(v -> sendCommandToScreen("status"));
        summary.setOnClickListener(v -> sendCommandToScreen("summary"));
        times.setOnClickListener(v -> sendCommandToScreen("times"));
        latest.setOnClickListener(v -> sendCommandToScreen("latest"));
        live.setOnClickListener(v -> startLiveReadings());
        stopLive.setOnClickListener(v -> stopLiveReadings());
        syncTime.setOnClickListener(v -> sendCommandToScreen("settime " + phoneTime()));
        log.setOnClickListener(v -> sendCommandToScreen("log"));
        download.setOnClickListener(v -> downloadCsv("download", "latest-week"));
        downloadAll.setOnClickListener(v -> downloadCsv("download all", "all-weeks"));
        resume.setOnClickListener(v -> sendCommandToScreen("resume"));
    }

    private Button button(String text) {
        Button button = new Button(this);
        button.setText(text);
        button.setAllCaps(false);
        return button;
    }

    private void requestBluetoothPermission() {
        if (Build.VERSION.SDK_INT >= 31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT}, 10);
        }
    }

    private void loadPairedDevices() {
        if (bluetoothAdapter == null) {
            statusText.setText("Bluetooth is not available on this phone.");
            return;
        }
        if (Build.VERSION.SDK_INT >= 31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            return;
        }

        Set<BluetoothDevice> bonded = bluetoothAdapter.getBondedDevices();
        pairedDevices.clear();
        List<String> names = new ArrayList<>();
        for (BluetoothDevice device : bonded) {
            pairedDevices.add(device);
            names.add(device.getName() + " (" + device.getAddress() + ")");
        }

        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, names);
        deviceSpinner.setAdapter(adapter);
        if (!pairedDevices.isEmpty()) {
            selectedDevice = pairedDevices.get(0);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == 10) {
            loadPairedDevices();
        }
    }

    private void connect() {
        if (selectedDevice == null) {
            show("No paired Bluetooth device selected.");
            return;
        }
        try {
            if (Build.VERSION.SDK_INT >= 31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                show("Bluetooth permission is required.");
                return;
            }
            socket = selectedDevice.createRfcommSocketToServiceRecord(SPP_UUID);
            bluetoothAdapter.cancelDiscovery();
            socket.connect();
            reader = new BufferedReader(new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8));
            writer = socket.getOutputStream();
            readAvailableFor(1200);
            runOnUiThread(() -> {
                connectButton.setEnabled(false);
                disconnectButton.setEnabled(true);
                statusText.setText("Connected to " + selectedDevice.getName());
            });
        } catch (IOException e) {
            disconnect();
            show("Connection failed: " + e.getMessage());
        }
    }

    private void disconnect() {
        try {
            if (socket != null) {
                socket.close();
            }
        } catch (IOException ignored) {
        }
        socket = null;
        reader = null;
        writer = null;
        liveMode = false;
        runOnUiThread(() -> {
            connectButton.setEnabled(true);
            disconnectButton.setEnabled(false);
        });
    }

    private void sendCommandToScreen(String command) {
        runInBackground(() -> {
            try {
                if (liveMode) {
                    stopLiveReadings();
                    sleep(300);
                }
                String response = sendCommand(command, 2500);
                runOnUiThread(() -> {
                    statusText.setText("Command: " + command);
                    recordsText.setText(response);
                });
            } catch (IOException e) {
                show("Command failed: " + e.getMessage());
            }
        });
    }

    private void downloadCsv(String command, String label) {
        runInBackground(() -> {
            try {
                if (liveMode) {
                    stopLiveReadings();
                    sleep(300);
                }
                String response = sendCommand(command, 7000);
                File directory = getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS);
                if (directory == null) {
                    throw new IOException("Documents folder unavailable.");
                }
                String filename = "water-logger-" + label + "-" + System.currentTimeMillis() + ".txt";
                File output = new File(directory, filename);
                try (FileOutputStream stream = new FileOutputStream(output)) {
                    stream.write(response.getBytes(StandardCharsets.UTF_8));
                }
                runOnUiThread(() -> {
                    statusText.setText("Saved download to:\n" + output.getAbsolutePath());
                    recordsText.setText(response);
                });
            } catch (IOException e) {
                show("Download failed: " + e.getMessage());
            }
        });
    }

    private void startLiveReadings() {
        runInBackground(() -> {
            ensureConnected();
            if (liveMode) {
                return;
            }
            liveMode = true;
            writer.write("live\n".getBytes(StandardCharsets.UTF_8));
            writer.flush();
            runOnUiThread(() -> statusText.setText("Live readings running"));

            liveThread = new Thread(() -> {
                StringBuilder latest = new StringBuilder();
                while (liveMode) {
                    try {
                        if (reader != null && reader.ready()) {
                            String line = reader.readLine();
                            if (line == null) {
                                break;
                            }
                            if (line.startsWith("LIVE ")) {
                                latest.setLength(0);
                                latest.append(line.replace(", ", "\n").replace("LIVE ", ""));
                                runOnUiThread(() -> recordsText.setText(latest.toString()));
                            }
                        } else {
                            sleep(100);
                        }
                    } catch (IOException e) {
                        show("Live read failed: " + e.getMessage());
                        break;
                    }
                }
            });
            liveThread.start();
        });
    }

    private void stopLiveReadings() {
        runInBackground(() -> {
            liveMode = false;
            if (writer != null) {
                writer.write("stop\n".getBytes(StandardCharsets.UTF_8));
                writer.flush();
            }
            runOnUiThread(() -> statusText.setText("Live readings stopped"));
        });
    }

    private String sendCommand(String command, long waitMs) throws IOException {
        ensureConnected();
        writer.write((command + "\n").getBytes(StandardCharsets.UTF_8));
        writer.flush();
        return readAvailableFor(waitMs);
    }

    private String readAvailableFor(long waitMs) throws IOException {
        StringBuilder response = new StringBuilder();
        long end = System.currentTimeMillis() + waitMs;
        while (System.currentTimeMillis() < end) {
            while (reader != null && reader.ready()) {
                response.append((char) reader.read());
            }
            sleep(80);
        }
        return response.toString().trim();
    }

    private void ensureConnected() throws IOException {
        if (socket == null || !socket.isConnected() || writer == null || reader == null) {
            throw new IOException("Not connected.");
        }
    }

    private String phoneTime() {
        SimpleDateFormat format = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US);
        return format.format(new Date());
    }

    private void runInBackground(Task task) {
        new Thread(() -> {
            try {
                task.run();
            } catch (Exception e) {
                show(e.getMessage());
            }
        }).start();
    }

    private void show(String message) {
        runOnUiThread(() -> {
            statusText.setText(message);
            Toast.makeText(this, message, Toast.LENGTH_LONG).show();
        });
    }

    private void sleep(long ms) {
        try {
            Thread.sleep(ms);
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        }
    }

    private interface Task {
        void run() throws Exception;
    }
}
