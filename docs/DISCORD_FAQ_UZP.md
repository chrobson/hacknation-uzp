**FAQ – Odwołania2JSON (wersja 1.0) | 1/4**

**1. Na czym polega wyzwanie Odwołania2JSON?**

Celem jest stworzenie aplikacji, która automatycznie analizuje dokumenty PDF związane z odwołaniami do Krajowej Izby Odwoławczej, rozpoznaje ich rodzaj (klasyfikuje) i dokonuje ekstrakcji zawartych w nich informacji w ustrukturyzowane dane JSON.

**2. Jakie dokumenty powinno obsługiwać rozwiązanie?**

Trzy rodzaje: odwołanie do KIO, pełnomocnictwo oraz potwierdzenie przelewu. Każdy dokument ma własną strukturę oczekiwanych danych.

**3. Czy aplikacja musi rozpoznawać rodzaj dokumentu?**

Tak. Jednym z elementów wyzwania jest automatyczna klasyfikacja dokumentu i zastosowanie odpowiedniego schematu ekstrakcji.

**4. Jaki powinien być wynik działania aplikacji?**

Dla każdego przetworzonego dokumentu aplikacja powinna wygenerować JSON zgodny z odpowiednim schematem udostępnionym w repozytorium.

**5. Jakie informacje należy wyodrębniać z dokumentów?**

Z odwołań [m.in](http://m.in). strony postępowania, dane zamówienia i zaskarżoną czynność; z pełnomocnictw – mocodawców, pełnomocników i podpisujących; z przelewów – kwotę, datę, rachunki i tytuł płatności.

**FAQ – Odwołania2JSON (wersja 1.0) | 2/4**

**6. Co zrobić, gdy dokument nie zawiera wymaganej informacji?**

Nie należy wymyślać brakujących danych. W polach, których schemat dopuszcza brak wartości, należy zastosować null zgodnie z udostępnionymi przykładami.

**7. Czy aplikacja powinna obsługiwać również zeskanowane dokumenty?**

Tak. Takie dokumenty występują w opisanym problemie. Rozwiązanie powinno więc uwzględniać zarówno PDF-y zawierające tekst, jak i dokumenty wymagające rozpoznawania tekstu przez OCR.

**8. Jakie dane treningowe otrzymują uczestnicy?**

Repozytorium zawiera co najmniej 39 zestawów przykładów. Każdy obejmuje trzy dokumenty PDF oraz odpowiadające im pliki JSON z danymi referencyjnymi.

**9. Czy dane testowe będą takie same jak treningowe?**

Nie. Organizator przewiduje osobny, nieudostępniony uczestnikom zbiór testowy. Rozwiązanie w związku z tym powinno poprawnie przetwarzać również nowe dokumenty. Wgląd w te dane można uzyskać na stoisku Urzędu Zamówień Publicznych.

**10. Jak będzie oceniana jakość rozwiązania?**

W preselekcji decyduje \[miara F1\]([https://www.flowhunt.io/pl/slownik/f1-score/](https://www.flowhunt.io/pl/slownik/f1-score/)) (100%). W etapie finałowym F1 odpowiada za 50% oceny, a pozostałe 50% dotyczy elastyczności i możliwości rozbudowy rozwiązania o nowe klasy dokumentów.

**FAQ – Odwołania2JSON (wersja 1.0) | 3/4**

**11. Czy można korzystać z modeli AI i zewnętrznych API?**

Wymagane są komponenty open source, w tym otwartoźródłowe modele językowe, dostępne do użytku bez ograniczeń i opłat licencyjnych. W trakcie hackathonu polecamy wykorzystać dostępne LLM przez API, jednak muszą to być modele które umożliwiają również lokalną instalacje. Adres API musi prowadzić do usługodawcy i serwera znajdującego się na terenie UE.

Zwracamy uwagę, że rozwiązania będą testowane na komputerze „biurowym”, bez GPU, więc decydowanie o „dużym modelu” uruchamianym lokalnie jest bardzo ryzykowne. Oznacza to, że rozwiązania jakie nam dostarczycie powinny zawierać klucz API do usługi, które wykorzystujecie. Obiecujemy nie nadużywać tokenów.

**12a. Czy konieczne jest przygotowanie CLI?**

Tak, to kluczowe jest przygotowanie CLI razem z instrukcją umożliwiające uruchomienie aplikacji z wiersza poleceń.

**12b. Czy konieczne jest przygotowanie interfejsu użytkownika?**

Nie jest konieczne, ale posiadanie będzie dodatkowo punktowane. Idealne rozwiązanie to GUI umożliwiające wgranie PDF, uruchomienie analizy i podgląd wygenerowanego JSON. Preferowany jest widok obok siebie: dokument źródłowy i wyodrębnione dane.



**FAQ – Odwołania2JSON (wersja 1.0) | 4/4**

**13. Czy rozwiązanie musi umożliwiać dodawanie nowych typów dokumentów?**

Na starcie wymagane są trzy wskazane typy. Możliwość dodawania kolejnych typów i pól przez konfigurację, bez przebudowy kodu, będzie szczególnie istotna podczas oceny finałowej.

**14. Czy należy stworzyć kompletny system do obsługi postępowań KIO?**

Nie. Przedmiotem wyzwania jest działający prototyp przetwarzający dokumenty PDF na JSON. Nie jest wymagane tworzenie pełnego systemu prowadzenia spraw odwoławczych.

**15. Co należy przygotować do zgłoszenia rozwiązania?**

Wymagane są tytuł projektu i link do działającego prototypu na GitHubie, umożliwiającego wgranie dokumentów oraz odczyt wyników ekstrakcji. Dodatkowo można dostarczyć dokumentację techniczną i wyniki własnych testów.

**16. Gdzie znajdę szczegółowe wytyczne techniczne?**

\[[https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026\](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026)](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026](https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026))



&nbsp;

&nbsp;

---



📢 **ODWOŁANIA2JSON | HACKNATION 2026 – PREZENTACJA WYZWANIA**

Cześć! 👋

Wrzucamy krótką prezentację, która w jednym miejscu pokazuje najważniejsze informacje o naszym wyzwaniu **Odwołania2JSON** przygotowanym przez Urząd Zamówień Publicznych.

🎯 **Na czym polega wyzwanie?**

Waszym zadaniem jest zbudowanie aplikacji, która automatycznie rozpoznaje dokumenty PDF, wyodrębnia z nich istotne informacje i zapisuje je w ustrukturyzowanym formacie JSON.

📂 **Jakie dane macie do dyspozycji?**

- 39 zestawów przykładowych danych

- 117 dokumentów PDF

- 3 rodzaje dokumentów: odwołanie, pełnomocnictwo i potwierdzenie przelewu

- Referencyjne pliki JSON oraz `ground_truth.yaml`

⚙️ **Na co zwracamy uwagę?**

Rozwiązanie powinno być oparte na komponentach open source, umożliwiać lokalne uruchomienie bez GPU oraz pozwalać na rozwój o kolejne typy dokumentów.

🏆 **Jak oceniamy rozwiązania?**

- Preselekcja: 100% – jakość ekstrakcji (F1)

- Finał: 50% – jakość ekstrakcji (F1), 50% – elastyczność i możliwość rozbudowy

💰 **Nagroda główna: 20 000 zł**

📎 **W załączonej prezentacji znajdziecie** opis problemu, zakres danych treningowych, przykład oczekiwanego prototypu, wymagania techniczne i kryteria oceny.

🔗 Materiały wyzwania: [https://hacknation.pl/zadania](https://hacknation.pl/zadania)

💬 Pytania i wątpliwości? Piszcie na Discordzie lub podejdźcie do naszego stoiska UZP podczas HackNation.

**Zrozum sprawę. Nie tylko dokument.** 🚀

Wysoka Piona,

Team UZP

---

Prośba ogromna o klaryfikacje, czy któraś z tych opcji jest właściwa?

1. LLMy OpenSource dostępne za darmo po API (ze świecą szukać, nie ma stabilnych, tylko reklamówki)

2. My mamy wystawić na swoim sprzęcie model, i aplikacja ma z niego korzystać po API

3. LLMy OpenSource dostępne płatnie po API  
Wszystkie 3 są zgodne z naszymi ustaleniami

tylko jak LLMy płatne, to potrzebujemy Waszych kluczy do oceny  
---



Jak dokładnie liczy sie F1?

**True Positive** - wartość występuje w JSONie i jest zgodna z oczekiwanym ground truth (w przypadku długich stringów takich jak nazwy firm, będzie brany pod uwagę procent zgodności, obecnie jest to 80%)

**True Negative** - wartości nie ma zarówno w JSONie jak i w ground truth

**False Positive** - wartość występuje tylko w JSON, lub wartość występuje w JSON i w ground truth, ale jest nieprawidłowa

**False Negative** - wartość nie występuje w JSON ale występuje w ground truth