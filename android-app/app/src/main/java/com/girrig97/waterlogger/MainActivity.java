package com.girrig97.waterlogger;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
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
        root.setPadding(dp(16), dp(16), dp(16), dp(16));
        root.setBackgroundColor(Color.rgb(244, 247, 250));

        TextView title = new TextView(this);
        title.setText("Water Logger");
        title.setTextSize(26);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.rgb(18, 32, 46));
        title.setPadding(0, 0, 0, dp(4));
        root.addView(title);

        TextView subtitle = new TextView(this);
        subtitle.setText("Creek sensor companion");
        subtitle.setTextSize(14);
        subtitle.setTextColor(Color.rgb(86, 102, 118));
        subtitle.setPadding(0, 0, 0, dp(14));
        root.addView(subtitle);

        LinearLayout connectionCard = card();
        connectionCard.addView(sectionTitle("Bluetooth"));

        deviceSpinner = new Spinner(this);
        connectionCard.addView(deviceSpinner, matchWrap());

        connectButton = button("Connect");
        disconnectButton = button("Disconnect");
        setButtonEnabled(disconnectButton, false);
        LinearLayout connectionButtons = row();
        connectionButtons.addView(connectButton, weightedWrap());
        connectionButtons.addView(space(dp(10), 1));
        connectionButtons.addView(disconnectButton, weightedWrap());
        connectionCard.addView(connectionButtons);
        root.addView(connectionCard, matchWrapBottom(dp(12)));

        LinearLayout controlsCard = card();
        addActionButtons(controlsCard);
        root.addView(controlsCard, matchWrapBottom(dp(12)));

        statusText = new TextView(this);
        statusText.setText("Select a paired Orange Pi Bluetooth device, then connect.");
        statusText.setTextSize(15);
        statusText.setTextColor(Color.rgb(18, 32, 46));
        statusText.setPadding(dp(14), dp(12), dp(14), dp(12));
        statusText.setBackground(rounded(Color.rgb(230, 239, 248), dp(8), Color.TRANSPARENT));
        root.addView(statusText, matchWrapBottom(dp(12)));

        recordsText = new TextView(this);
        recordsText.setTextSize(14);
        recordsText.setTextColor(Color.rgb(22, 28, 36));
        recordsText.setLineSpacing(0, 1.08f);
        recordsText.setPadding(dp(14), dp(14), dp(14), dp(14));
        recordsText.setTextIsSelectable(true);
        recordsText.setText("Output will appear here.");

        ScrollView scrollView = new ScrollView(this);
        scrollView.setBackground(rounded(Color.WHITE, dp(8), Color.rgb(218, 226, 234)));
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
        root.addView(sectionTitle("Readings"));
        Button status = button("System Status");
        Button summary = button("Record Count");
        Button times = button("List Record Times");
        Button latest = button("Latest Reading");
        Button live = button("Start Live Readings");
        Button stopLive = button("Stop Live Readings");

        addButtonRow(root, status, latest);
        addButtonRow(root, summary, times);
        addButtonRow(root, live, stopLive);

        root.addView(sectionTitle("Logging"));
        Button syncTime = button("Sync Time + Log");
        Button log = button("Log Fresh Reading");
        addButtonRow(root, syncTime, log);

        root.addView(sectionTitle("Files"));
        Button download = button("Download Latest Week");
        Button downloadAll = button("Download All Weeks");
        Button resume = button("Resume Normal Logging");
        addButtonRow(root, download, downloadAll);
        root.addView(resume, matchWrapTop(dp(8)));

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
        button.setTextSize(14);
        button.setMinHeight(dp(44));
        button.setPadding(dp(8), 0, dp(8), 0);
        setButtonEnabled(button, true);
        return button;
    }

    private void setButtonEnabled(Button button, boolean enabled) {
        button.setEnabled(enabled);
        button.setTextColor(enabled ? Color.WHITE : Color.rgb(100, 116, 139));
        int fill = enabled ? Color.rgb(21, 101, 192) : Color.rgb(226, 232, 240);
        int stroke = enabled ? Color.TRANSPARENT : Color.rgb(203, 213, 225);
        button.setBackground(rounded(fill, dp(7), stroke));
    }

    private TextView sectionTitle(String text) {
        TextView title = new TextView(this);
        title.setText(text);
        title.setTextColor(Color.rgb(71, 85, 99));
        title.setTextSize(12);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setPadding(0, dp(8), 0, dp(6));
        return title;
    }

    private LinearLayout card() {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(14), dp(8), dp(14), dp(14));
        card.setBackground(rounded(Color.WHITE, dp(8), Color.rgb(218, 226, 234)));
        return card;
    }

    private LinearLayout row() {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setPadding(0, dp(8), 0, 0);
        return row;
    }

    private void addButtonRow(LinearLayout root, Button left, Button right) {
        LinearLayout row = row();
        row.addView(left, weightedWrap());
        row.addView(space(dp(10), 1));
        row.addView(right, weightedWrap());
        root.addView(row, matchWrap());
    }

    private View space(int width, int height) {
        View view = new View(this);
        view.setLayoutParams(new LinearLayout.LayoutParams(width, height));
        return view;
    }

    private LinearLayout.LayoutParams matchWrap() {
        return new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
    }

    private LinearLayout.LayoutParams matchWrapBottom(int bottomMargin) {
        LinearLayout.LayoutParams params = matchWrap();
        params.setMargins(0, 0, 0, bottomMargin);
        return params;
    }

    private LinearLayout.LayoutParams matchWrapTop(int topMargin) {
        LinearLayout.LayoutParams params = matchWrap();
        params.setMargins(0, topMargin, 0, 0);
        return params;
    }

    private LinearLayout.LayoutParams weightedWrap() {
        return new LinearLayout.LayoutParams(
                0,
                LinearLayout.LayoutParams.WRAP_CONTENT,
                1
        );
    }

    private GradientDrawable rounded(int fillColor, int radius, int strokeColor) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fillColor);
        drawable.setCornerRadius(radius);
        if (strokeColor != Color.TRANSPARENT) {
            drawable.setStroke(1, strokeColor);
        }
        return drawable;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private void requestBluetoothPermission() {
        if (Build.VERSION.SDK_INT >= 31
                && (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED
                || checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) != PackageManager.PERMISSION_GRANTED)) {
            requestPermissions(new String[]{
                    Manifest.permission.BLUETOOTH_CONNECT,
                    Manifest.permission.BLUETOOTH_SCAN
            }, 10);
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
                setButtonEnabled(connectButton, false);
                setButtonEnabled(disconnectButton, true);
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
            setButtonEnabled(connectButton, true);
            setButtonEnabled(disconnectButton, false);
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
