# AVD 路徑定位模擬器

在地圖上畫路徑，讓 Android 模擬器 (AVD) 依照路徑、以指定速度更新定位。

## 安裝

```bash
cd avd-route-sim
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
4. 可用「搜尋地標 / 地址」欄位查詢地點（透過 OpenStreetMap Nominatim），點選搜尋結果會
   平移地圖並依目前模式套用座標：路徑模式下會清空原有路徑、把該地點設為新路徑的第一
   點；單點定位模式下會直接填入座標欄位。
5. 操作模式分兩種，切換時會清除另一模式殘留的資料（路徑點／單點座標與標記）：
   - **路徑模式**：在地圖上點擊建立路徑點（至少 2 點），可用「復原上一點」「清除路徑」
     調整；選擇速度預設（走路/跑步/騎車/開車）或自行輸入 km/h、確認 port 與更新間隔，
     需要不斷重複走同一條路徑就勾選「循環播放」，按「開始模擬」。程式會依速度沿路徑
     內插座標，每隔設定的秒數透過 emulator console 送出 `geo fix` 指令；AVD 上的定位
     會即時跟著移動。按「停止模擬」可隨時中斷；若切到單點定位模式或直接關閉網頁，
     也會自動停止模擬。
   - **單點定位模式**：在地圖上點擊或輸入「座標 (緯度, 經度)」，按「送出定位」直接
     對 AVD 送出一次 `geo fix`，適合快速測試單一位置（若路徑模擬正在執行，切換到此
     模式會自動先停止模擬）。

## 原理

- 路徑點之間的距離用 haversine 公式計算，依速度換算每個更新間隔要前進的公尺數，
  在相鄰兩點間線性內插出座標。
- 定位更新透過直接連線 emulator console（`127.0.0.1:<port>`）送出文字指令，
  若本機有 `~/.emulator_console_auth_token` 會自動帶入 `auth` 驗證。
- 若模擬器需要驗證但找不到 token，或 port 錯誤/AVD 未啟動，畫面上會顯示錯誤訊息。
- 地標／地址搜尋是瀏覽器端直接呼叫 OpenStreetMap 的 Nominatim API
  （`nominatim.openstreetmap.org/search`），不經過後端伺服器。
- 關閉分頁時會用 `navigator.sendBeacon` 通知伺服器停止模擬，避免忘記按「停止模擬」
  導致背景持續送出定位更新。

## 測試

```bash
pip install -r requirements-dev.txt
pytest
```

單元測試涵蓋路徑幾何運算（haversine、內插）與 API 輸入驗證（不合法格式、超出範圍的
經緯度、缺欄位等），emulator console 連線以假物件（fake）替換，不需要實際啟動 AVD。

## 已知限制

- 目前整條路徑只用單一速度；若需要中途變速，可分段畫路徑、多次調整速度後分次執行。
- 定位更新間隔最小 0.1 秒，過於頻繁對模擬器意義不大（GPS 更新本身也有延遲）。
- 循環播放走完一圈後會直接跳回起點重新開始（同方向），不是來回反向走。
