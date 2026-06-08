# Panduan Integrasi Android Studio — Prediksi Stok Menu

Dokumen ini berisi **semua file dan kode** yang perlu Anda tambahkan di project Android Studio DormFood untuk mengintegrasikan fitur prediksi stok menu dari ML API.

---

## Daftar File yang Perlu Ditambahkan / Diubah

| # | Aksi | File | Keterangan |
|---|------|------|------------|
| 1 | TAMBAH | `build.gradle (Module: app)` | Tambah dependency Retrofit |
| 2 | BUAT | `network/PrediksiApiService.kt` | Retrofit interface |
| 3 | BUAT | `network/RetrofitClient.kt` | Singleton Retrofit instance |
| 4 | BUAT | `model/PrediksiResponse.kt` | Data class response API |
| 5 | BUAT | `viewmodel/PrediksiViewModel.kt` | ViewModel untuk prediksi |
| 6 | BUAT | `ui/PrediksiStokScreen.kt` | UI Composable (atau XML) |
| 7 | UBAH | `AndroidManifest.xml` | Tambah internet permission |

---

## Langkah 1: Tambah Dependencies di `build.gradle`

Di file `build.gradle (Module: app)`, tambahkan di block `dependencies`:

```groovy
// Retrofit untuk HTTP request ke ML API
implementation("com.squareup.retrofit2:retrofit:2.9.0")
implementation("com.squareup.retrofit2:converter-gson:2.9.0")
implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

// Coroutines (kalau belum ada)
implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")

// ViewModel (kalau belum ada)
implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
```

Lalu **Sync Gradle**.

---

## Langkah 2: Tambah Internet Permission

Di `AndroidManifest.xml`, pastikan ada:

```xml
<manifest ...>
    <uses-permission android:name="android.permission.INTERNET" />
    
    <!-- Untuk akses localhost dari emulator -->
    <application
        android:usesCleartextTraffic="true"
        ... >
```

> **⚠️ PENTING:** `usesCleartextTraffic="true"` hanya untuk development (localhost). 
> Untuk production, gunakan HTTPS dan hapus setting ini.

---

## Langkah 3: Buat Model Response

Buat file baru: `com/zayyan/dormfood/ui/model/PrediksiResponse.kt`

```kotlin
package com.zayyan.dormfood.ui.model

/**
 * Response dari ML API /prediksi/{warungId}
 */
data class PrediksiResponse(
    val warungId: String = "",
    val status: String = "",           // "OK", "DATA_KURANG", "NO_DATA", "ERROR"
    val isDummy: Boolean = false,
    val totalMenu: Int = 0,
    val menuSiapPrediksi: Int = 0,
    val menuDataKurang: Int = 0,
    val menuNoData: Int = 0,
    val message: String? = null,
    val hasil: List<PrediksiMenu> = emptyList()
)

data class PrediksiMenu(
    val menu: String = "",
    val prediksi: Int? = null,          // null jika data tidak cukup
    val movingAverage7: Int? = null,
    val confidence: Double = 0.0,       // 0.0 - 1.0 (R² score)
    val status: String = "",            // "OK", "DATA_KURANG", "NO_DATA"
    val dataTersedia: Int = 0,
    val dataMinimum: Int = 14,
    val rataHarian: Double = 0.0,
    val message: String? = null
) {
    /**
     * Apakah prediksi bisa ditampilkan (ada angkanya)
     */
    val hasPrediksi: Boolean get() = prediksi != null

    /**
     * Label confidence untuk UI
     */
    val confidenceLabel: String get() = when {
        confidence >= 0.8 -> "Tinggi"
        confidence >= 0.5 -> "Sedang"
        confidence >= 0.3 -> "Rendah"
        else -> "Sangat Rendah"
    }

    /**
     * Warna confidence (hex color)
     */
    val confidenceColor: Long get() = when {
        confidence >= 0.8 -> 0xFF4CAF50  // Hijau
        confidence >= 0.5 -> 0xFFFF9800  // Orange
        confidence >= 0.3 -> 0xFFFF5722  // Merah terang
        else -> 0xFF9E9E9E              // Abu-abu
    }
}

/**
 * State keseluruhan untuk UI
 */
sealed class PrediksiUiState {
    object Loading : PrediksiUiState()
    object NoData : PrediksiUiState()
    data class DataKurang(val data: PrediksiResponse) : PrediksiUiState()
    data class Success(val data: PrediksiResponse) : PrediksiUiState()
    data class Error(val message: String) : PrediksiUiState()
    object ServerOffline : PrediksiUiState()
}
```

---

## Langkah 4: Buat Retrofit Service

Buat file baru: `com/zayyan/dormfood/network/RetrofitClient.kt`

```kotlin
package com.zayyan.dormfood.network

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {
    // === UBAH URL INI SESUAI DEPLOYMENT ===
    // Emulator Android: "http://10.0.2.2:5000"  (alias localhost)
    // Device fisik di WiFi yang sama: "http://192.168.x.x:5000"
    // Production: "https://your-api-domain.com"
    private const val BASE_URL = "http://10.0.2.2:5000/"

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    private val client = OkHttpClient.Builder()
        .addInterceptor(loggingInterceptor)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    val instance: Retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }
}
```

Buat file baru: `com/zayyan/dormfood/network/PrediksiApiService.kt`

```kotlin
package com.zayyan.dormfood.network

import com.zayyan.dormfood.ui.model.PrediksiResponse
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

interface PrediksiApiService {

    @GET("health")
    suspend fun healthCheck(): Response<Map<String, String>>

    @GET("prediksi/{warungId}")
    suspend fun getPrediksi(
        @Path("warungId") warungId: String,
        @Query("days") days: Int = 30
    ): Response<PrediksiResponse>

    @GET("prediksi/{warungId}/dummy")
    suspend fun getPrediksiDummy(
        @Path("warungId") warungId: String
    ): Response<PrediksiResponse>

    companion object {
        val api: PrediksiApiService by lazy {
            RetrofitClient.instance.create(PrediksiApiService::class.java)
        }
    }
}
```

---

## Langkah 5: Buat ViewModel

Buat file baru: `com/zayyan/dormfood/ui/viewmodel/PrediksiViewModel.kt`

```kotlin
package com.zayyan.dormfood.ui.viewmodel

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.zayyan.dormfood.network.PrediksiApiService
import com.zayyan.dormfood.ui.model.PrediksiResponse
import com.zayyan.dormfood.ui.model.PrediksiUiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class PrediksiViewModel : ViewModel() {

    private val api = PrediksiApiService.api

    private val _uiState = MutableStateFlow<PrediksiUiState>(PrediksiUiState.Loading)
    val uiState: StateFlow<PrediksiUiState> = _uiState

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing

    /**
     * Load prediksi dari ML API.
     * Otomatis menentukan UI state berdasarkan response.
     */
    fun loadPrediksi(warungId: String, days: Int = 30) {
        if (warungId.isBlank()) return

        viewModelScope.launch {
            _uiState.value = PrediksiUiState.Loading

            try {
                val response = api.getPrediksi(warungId, days)

                if (response.isSuccessful) {
                    val data = response.body()
                    if (data == null) {
                        _uiState.value = PrediksiUiState.Error("Response kosong")
                        return@launch
                    }

                    _uiState.value = when (data.status) {
                        "NO_DATA" -> PrediksiUiState.NoData
                        "DATA_KURANG" -> PrediksiUiState.DataKurang(data)
                        "OK" -> PrediksiUiState.Success(data)
                        "ERROR" -> PrediksiUiState.Error(data.message ?: "Terjadi kesalahan")
                        else -> PrediksiUiState.Error("Status tidak dikenal: ${data.status}")
                    }
                } else {
                    _uiState.value = PrediksiUiState.Error(
                        "Server error: ${response.code()}"
                    )
                }

            } catch (e: java.net.ConnectException) {
                Log.e("PrediksiVM", "Server offline", e)
                _uiState.value = PrediksiUiState.ServerOffline
            } catch (e: Exception) {
                Log.e("PrediksiVM", "Error loading prediksi", e)
                _uiState.value = PrediksiUiState.Error(
                    e.message ?: "Terjadi kesalahan tidak diketahui"
                )
            }
        }
    }

    /**
     * Refresh prediksi (pull-to-refresh)
     */
    fun refresh(warungId: String) {
        _isRefreshing.value = true
        viewModelScope.launch {
            loadPrediksi(warungId)
            _isRefreshing.value = false
        }
    }

    /**
     * Load data dummy untuk testing UI
     */
    fun loadDummy(warungId: String) {
        viewModelScope.launch {
            _uiState.value = PrediksiUiState.Loading
            try {
                val response = api.getPrediksiDummy(warungId)
                if (response.isSuccessful && response.body() != null) {
                    _uiState.value = PrediksiUiState.Success(response.body()!!)
                } else {
                    _uiState.value = PrediksiUiState.Error("Gagal load dummy data")
                }
            } catch (e: Exception) {
                _uiState.value = PrediksiUiState.ServerOffline
            }
        }
    }
}
```

---

## Langkah 6: Buat UI Screen (Jetpack Compose)

Buat file baru: `com/zayyan/dormfood/ui/screen/PrediksiStokScreen.kt`

```kotlin
package com.zayyan.dormfood.ui.screen

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.zayyan.dormfood.ui.model.PrediksiMenu
import com.zayyan.dormfood.ui.model.PrediksiUiState
import com.zayyan.dormfood.ui.viewmodel.PrediksiViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PrediksiStokScreen(
    warungId: String,
    warungName: String = "Warung",
    prediksiViewModel: PrediksiViewModel = viewModel()
) {
    val uiState by prediksiViewModel.uiState.collectAsState()
    val isRefreshing by prediksiViewModel.isRefreshing.collectAsState()

    // Load saat pertama kali
    LaunchedEffect(warungId) {
        prediksiViewModel.loadPrediksi(warungId)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Prediksi Stok — $warungName") },
                actions = {
                    IconButton(onClick = { prediksiViewModel.refresh(warungId) }) {
                        Icon(Icons.Default.Refresh, "Refresh")
                    }
                }
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            when (val state = uiState) {
                // === STATE: LOADING ===
                is PrediksiUiState.Loading -> {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator()
                            Spacer(modifier = Modifier.height(16.dp))
                            Text("Menganalisis data penjualan...")
                        }
                    }
                }

                // === STATE: SERVER OFFLINE ===
                is PrediksiUiState.ServerOffline -> {
                    EmptyStateView(
                        icon = Icons.Default.CloudOff,
                        title = "Server Prediksi Offline",
                        subtitle = "Server ML sedang tidak aktif. Coba lagi nanti.",
                        buttonText = "Coba Lagi",
                        onButtonClick = { prediksiViewModel.loadPrediksi(warungId) }
                    )
                }

                // === STATE: NO DATA ===
                is PrediksiUiState.NoData -> {
                    EmptyStateView(
                        icon = Icons.Default.BarChart,
                        title = "Data Belum Cukup",
                        subtitle = "Belum ada data pesanan selesai.\nFitur prediksi akan aktif setelah ada minimal 14 hari data pesanan.",
                        buttonText = null,
                        onButtonClick = {}
                    )
                }

                // === STATE: DATA KURANG (WARNING) ===
                is PrediksiUiState.DataKurang -> {
                    PrediksiListView(
                        data = state.data,
                        showWarning = true,
                        onRefresh = { prediksiViewModel.refresh(warungId) }
                    )
                }

                // === STATE: SUCCESS ===
                is PrediksiUiState.Success -> {
                    PrediksiListView(
                        data = state.data,
                        showWarning = false,
                        onRefresh = { prediksiViewModel.refresh(warungId) }
                    )
                }

                // === STATE: ERROR ===
                is PrediksiUiState.Error -> {
                    EmptyStateView(
                        icon = Icons.Default.Error,
                        title = "Terjadi Kesalahan",
                        subtitle = state.message,
                        buttonText = "Coba Lagi",
                        onButtonClick = { prediksiViewModel.loadPrediksi(warungId) }
                    )
                }
            }
        }
    }
}


@Composable
private fun PrediksiListView(
    data: com.zayyan.dormfood.ui.model.PrediksiResponse,
    showWarning: Boolean,
    onRefresh: () -> Unit
) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Dummy data banner
        if (data.isDummy) {
            item {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = Color(0xFFFFF3E0)
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Info,
                            contentDescription = null,
                            tint = Color(0xFFFF9800)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            "Ini adalah data contoh (dummy). " +
                            "Prediksi real akan aktif setelah ada cukup data pesanan.",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFE65100)
                        )
                    }
                }
            }
        }

        // Warning banner (data kurang)
        if (showWarning) {
            item {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = Color(0xFFFFF8E1)
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Warning,
                            contentDescription = null,
                            tint = Color(0xFFFFA000)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            "⚠️ Data pesanan masih sedikit. " +
                            "Hasil prediksi mungkin kurang akurat. " +
                            "Akurasi akan meningkat seiring bertambahnya data.",
                            style = MaterialTheme.typography.bodySmall,
                            color = Color(0xFFF57F17)
                        )
                    }
                }
            }
        }

        // Summary card
        item {
            SummaryCard(data)
        }

        // Menu items
        items(data.hasil) { menu ->
            PrediksiMenuCard(menu)
        }
    }
}


@Composable
private fun SummaryCard(data: com.zayyan.dormfood.ui.model.PrediksiResponse) {
    Card(
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                "Ringkasan Prediksi",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(12.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                StatItem(
                    value = "${data.menuSiapPrediksi}",
                    label = "Siap",
                    color = Color(0xFF4CAF50)
                )
                StatItem(
                    value = "${data.menuDataKurang}",
                    label = "Warning",
                    color = Color(0xFFFF9800)
                )
                StatItem(
                    value = "${data.menuNoData}",
                    label = "Belum Ada",
                    color = Color(0xFF9E9E9E)
                )
            }
        }
    }
}


@Composable
private fun StatItem(value: String, label: String, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            value,
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
            color = color
        )
        Text(
            label,
            fontSize = 12.sp,
            color = Color.Gray
        )
    }
}


@Composable
private fun PrediksiMenuCard(menu: PrediksiMenu) {
    val statusColor = when (menu.status) {
        "OK" -> Color(0xFF4CAF50)
        "DATA_KURANG" -> Color(0xFFFF9800)
        else -> Color(0xFF9E9E9E)
    }

    Card(
        shape = RoundedCornerShape(12.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Header: nama menu + status
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    menu.menu,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold
                )
                Surface(
                    color = statusColor.copy(alpha = 0.15f),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text(
                        when (menu.status) {
                            "OK" -> "✅ Akurat"
                            "DATA_KURANG" -> "⚠️ Estimasi"
                            else -> "❌ Tidak tersedia"
                        },
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        fontSize = 11.sp,
                        color = statusColor
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            if (menu.hasPrediksi) {
                // Prediksi tersedia
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    // Prediksi besok
                    Column {
                        Text("Prediksi Besok", fontSize = 11.sp, color = Color.Gray)
                        Text(
                            "${menu.prediksi} porsi",
                            fontSize = 20.sp,
                            fontWeight = FontWeight.Bold,
                            color = statusColor
                        )
                    }
                    // Rata-rata 7 hari
                    Column(horizontalAlignment = Alignment.End) {
                        Text("Rata-rata 7 hari", fontSize = 11.sp, color = Color.Gray)
                        Text(
                            "${menu.movingAverage7 ?: "-"} porsi",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                // Confidence bar
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        "Akurasi: ${menu.confidenceLabel} (${(menu.confidence * 100).toInt()}%)",
                        fontSize = 11.sp,
                        color = Color.Gray
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    LinearProgressIndicator(
                        progress = { menu.confidence.toFloat() },
                        modifier = Modifier
                            .weight(1f)
                            .height(6.dp)
                            .clip(RoundedCornerShape(3.dp)),
                        color = Color(menu.confidenceColor),
                        trackColor = Color(0xFFE0E0E0),
                    )
                }

                // Info tambahan
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    "Data: ${menu.dataTersedia} hari | Rata-rata harian: ${menu.rataHarian}",
                    fontSize = 10.sp,
                    color = Color.Gray
                )
            } else {
                // Prediksi tidak tersedia
                Text(
                    menu.message ?: "Data tidak cukup untuk prediksi",
                    fontSize = 13.sp,
                    color = Color.Gray,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth()
                )
            }
        }
    }
}


@Composable
private fun EmptyStateView(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    buttonText: String?,
    onButtonClick: () -> Unit
) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.padding(32.dp)
        ) {
            Icon(
                icon,
                contentDescription = null,
                modifier = Modifier.size(72.dp),
                tint = Color(0xFFBDBDBD)
            )
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                title,
                fontSize = 20.sp,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                subtitle,
                fontSize = 14.sp,
                color = Color.Gray,
                textAlign = TextAlign.Center
            )
            if (buttonText != null) {
                Spacer(modifier = Modifier.height(24.dp))
                Button(onClick = onButtonClick) {
                    Text(buttonText)
                }
            }
        }
    }
}
```

---

## Langkah 7: Cara Memanggil dari Halaman Warung

Di halaman warung Anda (misalnya di `WarungDetailScreen`), tambahkan tombol atau tab untuk membuka prediksi:

```kotlin
// Di halaman detail warung, tambahkan tombol ini:
Button(
    onClick = {
        // Navigasi ke PrediksiStokScreen
        // warungId = ID warung yang sedang dilihat (auth.currentUser.uid untuk pemilik)
        navController.navigate("prediksi_stok/$warungId")
    }
) {
    Icon(Icons.Default.TrendingUp, contentDescription = null)
    Spacer(modifier = Modifier.width(8.dp))
    Text("Prediksi Stok Menu")
}
```

Di `NavHost`, tambahkan route:

```kotlin
composable("prediksi_stok/{warungId}") { backStackEntry ->
    val warungId = backStackEntry.arguments?.getString("warungId") ?: ""
    PrediksiStokScreen(
        warungId = warungId,
        warungName = "Nama Warung"  // ambil dari argument atau state
    )
}
```

---

## Langkah 8: Konfigurasi URL Server

### Untuk Emulator Android:
```kotlin
// Di RetrofitClient.kt
private const val BASE_URL = "http://10.0.2.2:5000/"
// 10.0.2.2 = alias localhost di Android Emulator
```

### Untuk Device Fisik (WiFi sama):
```kotlin
// Cek IP komputer: ipconfig (Windows) / ifconfig (Mac/Linux)
private const val BASE_URL = "http://192.168.1.xxx:5000/"
```

### Untuk Production:
```kotlin
// Setelah deploy ke cloud
private const val BASE_URL = "https://your-api.railway.app/"
```

---

## Alur Kerja Lengkap

```
┌──────────────────────────────────────────────────────────────┐
│  1. Pemilik warung buka halaman "Prediksi Stok"              │
│                          │                                    │
│  2. Android panggil GET /prediksi/{warungId}                 │
│                          │                                    │
│  3. Flask API query Firestore (orders status=Selesai)        │
│                          │                                    │
│  4. Data diagregasi per menu per hari                        │
│                          │                                    │
│  5. Linear Regression prediksi besok                         │
│                          │                                    │
│  6. Response JSON dikirim ke Android                         │
│                          │                                    │
│  7. Android tampilkan berdasarkan status:                    │
│     ┌─────────────────────────────────────────┐              │
│     │ NO_DATA     → "Data belum cukup" (grey) │              │
│     │ DATA_KURANG → Prediksi + warning banner │              │
│     │ OK          → Prediksi normal           │              │
│     │ ServerOff   → "Server offline"          │              │
│     └─────────────────────────────────────────┘              │
└──────────────────────────────────────────────────────────────┘
```

---

## Testing Langkah demi Langkah

### Di sisi Python (Flask API):

```bash
# 1. Aktifkan virtual environment
cd dormfood-ml-api
.\venv\Scripts\activate        # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Seed dummy data (ganti WARUNG_ID dengan UID warung di Firestore)
python seed_dummy.py --seed --warung-id YOUR_WARUNG_ID

# 4. Jalankan server Flask
python app.py

# 5. Test di browser
#    http://localhost:5000/health
#    http://localhost:5000/prediksi/YOUR_WARUNG_ID
#    http://localhost:5000/prediksi/YOUR_WARUNG_ID/dummy

# 6. (Opsional) Jalankan test otomatis
python test_predict.py --warung-id YOUR_WARUNG_ID

# 7. Cleanup dummy data setelah selesai
python seed_dummy.py --cleanup --warung-id YOUR_WARUNG_ID
```

### Di sisi Android:

1. Pastikan Flask server berjalan (`python app.py`)
2. Buka project Android di Android Studio
3. Tambahkan semua file dari panduan ini
4. Sync Gradle
5. Jalankan di Emulator → navigasi ke halaman prediksi
6. Seharusnya tampil data prediksi dari API

---

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| `java.net.ConnectException` | Flask server belum jalan, atau URL salah |
| `cleartext traffic not permitted` | Tambah `usesCleartextTraffic="true"` di manifest |
| Response 500 dari server | Cek log Flask di terminal, mungkin Firestore error |
| Prediksi selalu 0 | Data order mungkin tidak berstatus "Selesai" |
| `NO_DATA` terus | Belum ada order selesai, jalankan `seed_dummy.py` |
