# Kompleksowa Dokumentacja Techniczna Potoku Analitycznego w BigQuery
---
## Wprowadzenie
Ten dokument stanowi kompletną i wyczerpującą dokumentację techniczną zaawansowanego potoku przetwarzania danych (data pipeline) w Google BigQuery. System został zaprojektowany od podstaw w celu analizy danych z mediów społecznościowych (Instagram), pozyskiwanych za pośrednictwem platformy Apify. Głównym celem jest stworzenie w pełni zautomatyzowanego silnika analitycznego do identyfikacji wartościowych treści (leady), scoringu postów, wykrywania trendów, anomalii (viral content) oraz segmentacji użytkowników za pomocą uczenia maszynowego.

Niniejsza dokumentacja jest kulminacją i syntezą wiedzy projektowej, prezentując ewolucję systemu od najwcześniejszych, prostych zapytań i modeli danych, po finalną, dojrzałą i odporną na błędy architekturę. Każde polecenie, każda funkcja i każda decyzja projektowa zostanie tutaj szczegółowo omówiona.
---
## Sekcja 1: Architektura i Ewolucja Projektu
Zrozumienie obecnej, dojrzałej architektury wymaga spojrzenia na jej ewolucję i problemy, które kształtowały jej finalny projekt.
### **1.1. Koncepcja Początkowa: Architektura Warstwowa**
U podstaw projektu od samego początku leżał sprawdzony, trzywarstwowy model danych, który stał się fundamentem całej architektury:
*   **WARSTWA RAW:** Przechowywanie surowych, niezmienionych danych źródłowych. Stanowi to "jezioro danych" (Data Lake), które gwarantuje, że żadne informacje nie zostaną utracone i umożliwia ponowne przetworzenie danych w przyszłości.
*   **WARSTWA CLEAN / CORE:** Przechowywanie danych oczyszczonych, zwalidowanych, ustrukturyzowanych i zintegrowanych. Tabele w tej warstwie stanowią "jedyne źródło prawdy" (Single Source of Truth) dla całej organizacji.
*   **WARSTWA ANALYTICS / MART:** Przechowywanie danych wzbogaconych, zagregowanych i przygotowanych specjalnie pod kątem konkretnych analiz, modeli uczenia maszynowego czy dashboardów.
### **1.2. Wczesne Wyzwania i Kluczowe Rozwiązania Techniczne**
W miarę rozwoju projektu napotkano na szereg technicznych wyzwań, których rozwiązanie zdefiniowało dojrzałość obecnego potoku:
*   **Problem Niejednoznacznych Nazw Kolumn:** Przy pierwszych próbach łączenia tabel (np. profili i postów) pojawił się klasyczny błąd `ambiguous name` dla kolumn o tych samych nazwach (np. `scraped_at`).
    *   **Rozwiązanie:** Wprowadzenie rygorystycznej zasady stosowania **aliasów** zarówno dla tabel (np. `profiles AS p`), jak i dla kolumn w klauzuli `SELECT` (np. `p.scraped_at AS profile_scraped_at`), co zapewniło jednoznaczność i czytelność kodu.
*   **Problem Niestabilności Potoku i Duplikacji Danych:** Początkowe próby z użyciem `CREATE TABLE IF NOT EXISTS` w połączeniu ze zmieniającym się schematem prowadziły do błędów `Unrecognized name`. Co więcej, proste operacje `INSERT` powodowały duplikowanie danych przy wielokrotnym uruchamianiu potoku.
    *   **Rozwiązanie:** Zastosowanie dwóch fundamentalnych zmian:
        1.  **`CREATE OR REPLACE TABLE`**: Zapewniło, że schemat tabeli jest zawsze zgodny z definicją w kodzie, eliminując błędy związane z `schema drift`.
        2.  **`MERGE` (UPSERT)**: Zastąpienie prostych `INSERT`-ów operacją `MERGE` zagwarantowało **idempotentność** potoku. Oznacza to, że potok można uruchamiać wielokrotnie na tych samych danych, a wynik w tabelach `CORE` zawsze będzie poprawny i spójny, bez duplikatów.
---
## Sekcja 2: Analiza Techniczna Finalnego Potoku Analitycznego
Poniżej znajduje się szczegółowa, krok po kroku, analiza dojrzałej wersji potoku, który stanowi serce systemu analitycznego.
### **Etap 0: Inicjalizacja Schematu (Schema Safety)**
> **Cel Etapu:** Gwarancja istnienia i poprawności struktury kluczowych tabel przed rozpoczęciem operacji zapisu. Jest to krok prewencyjny, zapewniający spójność i bezpieczeństwo potoku.

**Pełne Polecenie SQL:**
```sql
-- Definiuje strukturę tabeli posts, nie ładując żadnych danych
CREATE OR REPLACE TABLE `x-object-491309-b5.app_insta.posts` (
    post_id STRING,
    url STRING,
    ownerUsername STRING,
    ownerFullName STRING,
    caption STRING,
    timestamp TIMESTAMP,
    likesCount INT64,
    commentsCount INT64,
    hashtags ARRAY<STRING>
);

-- Definiuje strukturę tabeli profiles
CREATE OR REPLACE TABLE `x-object-491309-b5.app_insta.profiles` (
    username STRING,
    bio STRING,
    external_url STRING,
    followers INT64
);
```
**Szczegółowa Analiza Kodu:**
*   `CREATE OR REPLACE TABLE`: Użycie tej instrukcji w trybie definicji schematu (bez klauzuli `AS SELECT`) tworzy pustą tabelę z zadaną strukturą lub zastępuje istniejącą, jeśli jej schemat miałby się różnić. Jest to najlepsza praktyka zapewniająca, że dalsze etapy, takie jak `MERGE`, zawsze będą operować na poprawnie zdefiniowanej tabeli docelowej.
*   `ARRAY<STRING>`: Deklaracja kolumny `hashtags` jako tablicy. Jest to natywny, wysoce zoptymalizowany typ danych w BigQuery, który pozwala na efektywne przechowywanie i odpytywanie list wartości bez potrzeby tworzenia dodatkowej tabeli relacyjnej, co znacząco upraszcza zapytania i zwiększa ich wydajność.
---
### **Etap 1: Przetwarzanie Wstępne (Staging)**
> **Cel Etapu:** Transformacja surowych danych JSON na w pełni ustrukturyzowaną, oczyszczoną i zwalidowaną tabelę tymczasową `stg_posts`.

**Pełne Polecenie SQL:**
```sql
CREATE OR REPLACE TABLE `x-object-491309-b5.app_insta.stg_posts` AS
SELECT
    run_id,
    JSON_VALUE(data, '$.url') AS url,
    REGEXP_EXTRACT(JSON_VALUE(data, '$.url'), r'/p/([^/]+)/') AS post_id,
    LOWER(JSON_VALUE(data, '$.ownerUsername')) AS ownerUsername,
    SAFE_CAST(JSON_VALUE(data, '$.timestamp') AS TIMESTAMP) AS timestamp,
    SAFE_CAST(JSON_VALUE(data, '$.likesCount') AS INT64) AS likesCount,
    SAFE_CAST(JSON_VALUE(data, '$.commentsCount') AS INT64) AS commentsCount,
    ARRAY(
        SELECT LOWER(JSON_VALUE(x))
        FROM UNNEST(JSON_QUERY_ARRAY(data, '$.hashtags')) x
    ) AS hashtags
FROM `x-object-491309-b5.app_insta.raw_posts`;
```
**Szczegółowa Analiza Kodu:**
*   `JSON_VALUE(data, '$.json_path')`: Służy do wyciągania wartości skalarnych z obiektu JSON. Kluczowe dla transformacji danych z postaci nieustrukturyzowanej do relacyjnej.
*   `REGEXP_EXTRACT(string, r'regex')`: Użycie wyrażenia regularnego do wyparowania `post_id` z adresu URL. Jest to niezwykle solidna metoda, która uniezależnia potok od istnienia pola `id` w danych źródłowych.
*   `LOWER(string)`: Niezbędna operacja normalizacji. Sprowadzenie nazw użytkowników i hashtagów do małych liter jest kluczowe dla zapewnienia spójności danych i uniknięcia problemów przy operacjach `JOIN` i `GROUP BY`.
*   `SAFE_CAST(value AS TYPE)`: Jedna z najważniejszych funkcji zapewniających odporność potoku. W przypadku nieudanej konwersji typu (np. z tekstu na liczbę), zwraca `NULL` zamiast przerywać całe zapytanie. To gwarantuje wysoką niezawodność (robustness) systemu.
*   `UNNEST(JSON_QUERY_ARRAY(...))`: Zaawansowana technika do przetwarzania zagnieżdżonych tablic. `JSON_QUERY_ARRAY` wyciąga tablicę z JSON, `UNNEST` przekształca ją w zbiór wierszy, co pozwala na zastosowanie operacji (`LOWER`) na każdym elemencie z osobna, a `ARRAY(...)` ponownie agreguje wyniki do postaci tablicy BigQuery.
---
### **Etap 2: Aktualizacja Tabeli Rdzennej `posts` (Core Integration)**
> **Cel Etapu:** Zasilenie głównej tabeli `posts` danymi z warstwy stagingowej w sposób idempotentny. Etap ten aktualizuje istniejące posty i wstawia nowe, unikając duplikatów.

**Pełne Polecenie SQL:**
```sql
MERGE `x-object-491309-b5.app_insta.posts` T
USING `x-object-491309-b5.app_insta.stg_posts` S
ON T.post_id = S.post_id
WHEN MATCHED AND S.timestamp > T.timestamp THEN
    UPDATE SET
        caption = S.caption,
        likesCount = S.likesCount,
        commentsCount = S.commentsCount,
        hashtags = S.hashtags,
        timestamp = S.timestamp
WHEN NOT MATCHED THEN
    INSERT (post_id, url, ownerUsername, caption, timestamp, likesCount, commentsCount, hashtags)
    VALUES (S.post_id, S.url, S.ownerUsername, S.caption, S.timestamp, S.likesCount, S.commentsCount, S.hashtags);
```
**Szczegółowa Analiza Kodu:**
*   `MERGE`: Jest to serce logiki integracyjnej potoku. Realizuje operację `UPSERT`, która jest znacznie bardziej wydajna i bezpieczna niż ręczne wykonywanie `UPDATE`, a następnie `INSERT`.
*   `ON T.post_id = S.post_id`: Warunek łączenia, który określa, w jaki sposób wiersze ze źródła (`S`) mają być dopasowywane do wierszy w tabeli docelowej (`T`). `post_id` jest tutaj kluczem biznesowym posta.
*   `WHEN MATCHED AND S.timestamp > T.timestamp`: Klauzula definiująca akcję, gdy post już istnieje. Dodatkowy warunek `S.timestamp > T.timestamp` jest kluczowy dla **integralności czasowej danych** – aktualizacja nastąpi tylko, gdy nowe dane są "świeższe". Zapobiega to nadpisywaniu aktualnych statystyk starszymi.
*   `WHEN NOT MATCHED THEN INSERT`: Klauzula definiująca akcję, gdy post jest nowy. Zostanie on wstawiony do tabeli `posts` jako nowy rekord.
---
### **Etap 3: Inżynieria Cech (Feature Engineering)**
> **Cel Etapu:** Wzbogacenie czystych danych o nowe, analityczne metryki (cechy), które będą stanowić podstawę dla dalszych analiz, scoringu i modeli ML.

**Pełne Polecenie SQL:**
```sql
CREATE OR REPLACE TABLE `x-object-491309-b5.app_insta.post_features` AS
SELECT
    post_id, url, ownerUsername, caption, timestamp, likesCount, commentsCount, hashtags,
    ARRAY_LENGTH(hashtags) AS hashtag_count,
    LENGTH(IFNULL(caption,'')) AS caption_length,
    EXTRACT(HOUR FROM timestamp) AS hour,
    (COALESCE(likesCount,0) + COALESCE(commentsCount,0)) AS engagement,
    REGEXP_CONTAINS(LOWER(IFNULL(caption,'')), r't\.me|telegram') AS has_telegram_post,
    REGEXP_CONTAINS(LOWER(IFNULL(caption,'')), r'dm|contact|offer') AS is_lead
FROM `x-object-491309-b5.app_insta.posts`;
```
**Szczegółowa Analiza Kodu:**
*   `ARRAY_LENGTH(hashtags)`: Zwraca liczbę hashtagów w poście. Może służyć jako wskaźnik "spamowości" lub strategii marketingowej.
*   `COALESCE(likesCount,0) + COALESCE(commentsCount,0)`: Oblicza kluczową metrykę `engagement`. Funkcja `COALESCE` jest tu użyta jako zabezpieczenie, traktując ewentualne wartości `NULL` jako zero.
*   `REGEXP_CONTAINS(...)`: Przykład **inżynierii cech opartej na regułach biznesowych**. Funkcja ta tworzy flagi `TRUE/FALSE` (np. `is_lead`) na podstawie obecności słów kluczowych w tekście, co pozwala na kategoryzację postów bez użycia skomplikowanych modeli NLP.
---
### **Etap 4: Wzbogacanie Danych o Profile (Enrichment)**
> **Cel Etapu:** Stworzenie pełnego, 360-stopniowego obrazu posta przez połączenie cech posta z cechami jego autora, które są przetwarzane w analogiczny sposób (Staging + Merge + Feature Engineering).

**Pełne Polecenie SQL:**
```sql
CREATE OR REPLACE TABLE `x-object-491309-b5.app_insta.enriched_posts` AS
SELECT
    p.*, -- Wszystkie kolumny z tabeli post_features
    pr.bio, pr.followers, pr.has_telegram_bio, pr.has_telegram_link
FROM `x-object-491309-b5.app_insta.post_features` p
LEFT JOIN `x-object-491309-b5.app_insta.profile_features` pr ON p.ownerUsername = pr.username;
```
**Szczegółowa Analiza Kodu:**
*   `LEFT JOIN`: Wybór `LEFT JOIN` jest istotny. Gwarantuje on, że w wyniku znajdą się **wszystkie** posty, nawet jeśli z jakiegoś powodu nie udało się pobrać danych o profilu ich autora. W takim przypadku kolumny z tabeli `profile_features` będą miały wartość `NULL`, ale post nie zostanie utracony z potoku.
---
### **Etap 5: Scoring Postów (Scoring)**
> **Cel Etapu:** Przypisanie każdemu postowi `final_score`, który odzwierciedla jego wartość biznesową na podstawie ważonej formuły.

**Pełne Polecenie SQL:**
```sql
CREATE OR REPLACE TABLE `x-object-491309-b5.app_insta.scored_posts` AS
SELECT
    *,
    -- Normalizacja zaangażowania do skali 0-1, aby umożliwić porównywanie
    SAFE_DIVIDE(engagement, MAX(engagement) OVER()) AS engagement_norm,
    -- Współczynnik "świeżości" posta, malejący wykładniczo z czasem
    EXP(-0.04 * TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp, HOUR)) AS freshness,
    -- Wynik końcowy (ważona średnia cech)
    (
        SAFE_DIVIDE(engagement, MAX(engagement) OVER()) * 0.35 +
        IF(is_lead, 1, 0) * 0.25 +
        IF(has_telegram_post OR has_telegram_bio OR has_telegram_link, 1, 0) * 0.25 +
        EXP(-0.04 * TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), timestamp, HOUR)) * 0.15
    ) AS final_score
FROM `x-object-491309-b5.app_insta.enriched_posts`;
```
**Szczegółowa Analiza Kodu:**
*   `MAX(engagement) OVER()`: Jest to **funkcja okna analitycznego**. Oblicza maksymalne zaangażowanie w całym zbiorze danych, ale zwraca tę wartość dla każdego wiersza, co pozwala na **normalizację** (`engagement_norm`) i obiektywne porównywanie postów o różnej skali popularności.
*   `EXP(-0.04 * TIMESTAMP_DIFF(...))`: Funkcja wykładnicza modelująca **zanik wartości posta w czasie** (`freshness`). `TIMESTAMP_DIFF` oblicza wiek posta. Im post starszy, tym jego `freshness` jest bliższy zeru.
*   `final_score`: Jest to **ważona średnia arytmetyczna** obliczonych cech. Wagi (0.35, 0.25, etc.) decydują o priorytetach modelu scoringowego i mogą być elastycznie modyfikowane w zależności od strategii biznesowej.
---
### **Etap 6: Deduplikacja (Deduplication)**
> **Cel Etapu:** Wyeliminowanie zduplikowanych postów, które mogły zostać pobrane wielokrotnie w różnych przebiegach, pozostawiając tylko jedną, najlepszą wersję każdego posta (tę z najwyższym `final_score`).

**Pełne Polecenie SQL:**
```sql
CREATE OR REPLACE TABLE `x-object-491309-b5.app_insta.dedup_posts` AS
SELECT * EXCEPT (row_num)
FROM (
    SELECT *, ROW_NUMBER() OVER(PARTITION BY post_id ORDER BY final_score DESC) as row_num
    FROM `x-object-491309-b5.app_insta.scored_posts`
) WHERE row_num = 1;
```
**Szczegółowa Analiza Kodu:**
*   `ROW_NUMBER() OVER(PARTITION BY post_id ORDER BY final_score DESC)`: Kolejna kluczowa funkcja okna. `PARTITION BY post_id` grupuje wszystkie wystąpienia tego samego posta, a `ORDER BY final_score DESC` sortuje je od najlepszego do najgorszego. `ROW_NUMBER()` przypisuje kolejny numer w każdej grupie. Wersja z najwyższym wynikiem zawsze otrzyma `row_num = 1`.
*   `WHERE row_num = 1`: Prosta, ale elegancka filtracja, która pozostawia tylko najlepszą wersję każdego posta.
---
### **Etap 7: Wykrywanie Anomalii (Anomaly Detection)**
> **Cel Etapu:** Automatyczna identyfikacja postów o ponadprzeciętnej popularności (wirusowych) za pomocą analizy statystycznej.

**Pełne Polecenie SQL:**
```sql
CREATE OR REPLACE TABLE `x-object-491309-b5.app_insta.viral_anomalies` AS
WITH stats AS (
    SELECT AVG(engagement) AS avg_eng, STDDEV(engagement) AS std_eng
    FROM `x-object-491309-b5.app_insta.dedup_posts`
)
SELECT
    p.post_id, p.engagement,
    SAFE_DIVIDE(p.engagement - s.avg_eng, s.std_eng) AS z_score,
    (p.engagement > s.avg_eng + 2 * s.std_eng) AS is_viral
FROM `x-object-491309-b5.app_insta.dedup_posts` p
CROSS JOIN stats s;
```
**Szczegółowa Analiza Kodu:**
*   `WITH stats AS (...)`: Użycie Common Table Expression (CTE) do jednorazowego obliczenia średniego zaangażowania (`avg_eng`) i odchylenia standardowego (`std_eng`) dla całego zbioru.
*   `CROSS JOIN`: Łączy każdy wiersz z tabeli postów z jednowierszową tabelą `stats`, co jest wydajnym sposobem na udostępnienie globalnych statystyk każdemu wierszowi do obliczeń.
*   `z_score`: Oblicza, o ile odchyleń standardowych zaangażowanie danego posta odbiega od średniej. Jest to standardowa miara statystyczna do wykrywania wartości odstających.
*   `is_viral`: Prosta reguła biznesowa. Post jest uznawany za wirusowy, jeśli jego zaangażowanie jest o więcej niż 2 odchylenia standardowe powyżej średniej.
---
### **Etap 8: Uczenie Maszynowe - Segmentacja (ML Clustering)**
> **Cel Etapu:** Automatyczna segmentacja postów na grupy o podobnych cechach za pomocą modelu K-Means wbudowanego w BigQuery ML.

**Pełne Polecenie SQL:**
```sql
-- Tworzenie i trenowanie modelu
CREATE OR REPLACE MODEL `x-object-491309-b5.app_insta.lead_kmeans_model`
OPTIONS(model_type='kmeans', num_clusters=5) AS
SELECT engagement, hashtag_count, hour, followers FROM `x-object-491309-b5.app_insta.dedup_posts` WHERE engagement IS NOT NULL;

-- Użycie modelu do predykcji i zapisanie wyników
CREATE OR REPLACE TABLE `x-object-491309-b5.app_insta.lead_clusters` AS
SELECT *
FROM ML.PREDICT(
    MODEL `x-object-491309-b5.app_insta.lead_kmeans_model`,
    (
        SELECT post_id, engagement, hashtag_count, hour, followers
        FROM `x-object-491309-b5.app_insta.dedup_posts`
    )
);
```
**Szczegółowa Analiza Kodu:**
*   `CREATE OR REPLACE MODEL`: Polecenie BigQuery ML, które trenuje model uczenia maszynowego. `OPTIONS(model_type='kmeans', num_clusters=5)` instruuje BigQuery, aby użyć algorytmu K-Means do znalezienia 5 naturalnych skupisk (klastrów) w danych.
*   `SELECT engagement, ...`: Definiuje cechy (features), na podstawie których model ma się uczyć i grupować dane.
*   `ML.PREDICT(MODEL ..., SELECT ...)`: Po wytrenowaniu modelu, funkcja `ML.PREDICT` używa go do przypisania każdego posta do jednego z 5 klastrów. Wynikiem jest nowa tabela `lead_clusters`, która zawiera `post_id` oraz `CENTROID_ID` (numer klastra), co pozwala na dalszą analizę segmentów.
---
### **Etap 9: Tworzenie Widoków Analitycznych (Dashboard Views)**
> **Cel Etapu:** Stworzenie zoptymalizowanych, gotowych do użycia widoków (`VIEW`), które będą służyć jako źródło danych dla zewnętrznych narzędzi BI (np. Looker Studio, Power BI) lub aplikacji.

**Pełne Polecenie SQL:**
```sql
CREATE OR REPLACE VIEW `x-object-491309-b5.app_insta.v_dashboard_leads` AS
SELECT
    p.post_id, p.url, p.caption, p.final_score, p.engagement, p.followers, c.CENTROID_ID
FROM `x-object-491309-b5.app_insta.dedup_posts` p
JOIN `x-object-491309-b5.app_insta.lead_clusters` c ON p.post_id = c.post_id
WHERE p.is_lead = TRUE
ORDER BY p.final_score DESC
LIMIT 1000;
```
**Szczegółowa Analiza Kodu:**
*   `CREATE OR REPLACE VIEW`: Tworzy widok, który jest wirtualną tabelą opartą na zapytaniu. Widok nie przechowuje danych, lecz wykonuje zapytanie za każdym razem, gdy jest odpytywany, co gwarantuje dostęp do najświeższych danych.
*   **Logika Widoku:** Widok ten jest zoptymalizowany pod konkretny cel – dostarczenie listy 1000 najlepszych, aktualnych leadów. Łączy on dane z kilku tabel, filtruje (`WHERE p.is_lead = TRUE`), sortuje i ogranicza wyniki, ukrywając całą złożoność potoku przed użytkownikiem końcowym.
---
