# AVD 路徑定位模擬器

在地圖上畫路徑，讓 Android 模擬器 (AVD) 依照路徑、以指定速度更新定位。

## 安裝

```bash
cd avd_route_sim
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## 使用

1. 先啟動要模擬的 AVD（Android Studio 或 `emulator -avd <name>`）。
   確認 console port（預設 `5554`，多開時會是 `5556`、`5558`...，可用 `adb devices` 查看，
   格式為 `emulator-5554`）。
2. 執行伺服器：

   ```bash
   python app.py
   ```

3. 瀏覽器打開 <http://localhost:8765>。（不是 5000，因為那個 port 在 macOS 上預設被
   AirPlay Receiver 佔用）
4. 在地圖上點擊建立路徑點（至少 2 點），可用「復原上一點」「清除路徑」調整。
5. 選擇速度預設（走路/跑步/騎車/開車）或自行輸入 km/h、確認 port 與更新間隔，
   需要不斷重複走同一條路徑就勾選「循環播放」，按「開始模擬」。
6. 程式會依速度沿路徑內插座標，每隔設定的秒數透過 emulator console 送出
   `geo fix` 指令；AVD 上的定位會即時跟著移動。按「停止模擬」可隨時中斷。

## 原理

- 路徑點之間的距離用 haversine 公式計算，依速度換算每個更新間隔要前進的公尺數，
  在相鄰兩點間線性內插出座標。
- 定位更新透過直接連線 emulator console（`127.0.0.1:<port>`）送出文字指令，
  若本機有 `~/.emulator_console_auth_token` 會自動帶入 `auth` 驗證。
- 若模擬器需要驗證但找不到 token，或 port 錯誤/AVD 未啟動，畫面上會顯示錯誤訊息。

## 已知限制

- 目前整條路徑只用單一速度；若需要中途變速，可分段畫路徑、多次調整速度後分次執行。
- 定位更新間隔最小 0.1 秒，過於頻繁對模擬器意義不大（GPS 更新本身也有延遲）。
- 循環播放走完一圈後會直接跳回起點重新開始（同方向），不是來回反向走。
