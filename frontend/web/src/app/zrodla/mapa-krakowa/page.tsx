import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Źródło mapy dzielnic Krakowa — Homies" };

export default function KrakowMapSourcePage() {
  return (
    <article className="container" style={{ paddingBlock: 40, maxWidth: 800 }}>
      <Link href="/">← Homies</Link>
      <h1>Mapa dzielnic Krakowa — źródło danych</h1>
      <p>Granice 18 dzielnic pochodzą z Gminy Miejskiej Kraków, Portalu MSIP Obserwatorium. Mapa ma charakter poglądowy; nie jest dokumentem urzędowym.</p>
      <dl>
        <dt>Źródło</dt>
        <dd><a href="https://msip.krakow.pl/dataset/1483">MSIP — Podział administracyjny: dzielnice</a></dd>
        <dt>Data wygenerowania pobranego pliku</dt>
        <dd>5 grudnia 2025, 10:00:39 — według informacji dołączonej przez wydawcę. Nie jest to potwierdzenie aktualności wszystkich granic na dzień pobrania.</dd>
        <dt>Data pobrania przez Homies</dt>
        <dd>3 listopada 2026</dd>
        <dt>Opracowanie przez Homies</dt>
        <dd>Jednolita skala i odwrócenie osi pionowej do wyświetlenia mapy z północą u góry. Zachowano wszystkie punkty i pierścienie granic; dodano kolory, numery i interakcję. Bez podkładu mapowego i bez punktów adresowych.</dd>
      </dl>
      <h2>Dzielnice a okolice w wyszukiwarce</h2>
      <p>Mapa przedstawia administracyjny podział miasta. Okolice używane do wyszukiwania ofert, takie jak Kazimierz, nie są tym samym podziałem. Wybranie dzielnicy na mapie nie włącza filtra ofert. Przejścia do obsługiwanych okolic są opisane osobno pod mapą.</p>
      <h2>Warunki wykorzystania</h2>
      <p>Źródło i zasady: <a href="https://msip.krakow.pl/getHtml?dok_id=228972">Regulamin MSIP</a>, <a href="https://www.bip.krakow.pl/?dok_id=56559&metka=1">zasady dla danych MSIP</a> oraz <a href="https://www.bip.krakow.pl/?dok_id=48482">zasady ponownego wykorzystywania informacji sektora publicznego</a>.</p>
      <p>Gmina Miejska Kraków nie odpowiada za szkody wynikające z wykorzystania lub dalszego udostępniania informacji z naruszeniem warunków jej udostępnienia albo obowiązującego prawa. Pełny zakres odpowiedzialności określa punkt II zasad ponownego wykorzystywania wskazanych powyżej.</p>
    </article>
  );
}
