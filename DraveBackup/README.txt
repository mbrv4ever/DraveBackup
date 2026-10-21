DraveBackup - geplande lokale back-up van je mappen
===================================================

Dravenlock - lokaal en offline. Er gaat niets naar internet.

STARTEN
-------
Dubbelklik run.bat (eerste keer installeert die zichzelf; Python 3.10 t/m 3.13
nodig). Werkt iets niet, gebruik start-debug.bat: die toont de fouten.

EEN TAAK MAKEN
--------------
Nieuw -> geef een naam, voeg een of meer BRONmappen toe (wat je wilt back-uppen)
en kies een DOEL (bv. een externe schijf, of waar de zip moet komen).

SOORT BACK-UP
-------------
- Sync/kopie: kopieert bestanden naar de doelmap. Incrementeel slaat ongewijzigde
  bestanden over (sneller). Spiegelen verwijdert extra bestanden op het doel die
  niet meer in de bron staan - handig voor een exacte kopie, maar het wist echt.
- Zip: pakt alles in een zip met datum/tijd in de naam.

PLANNEN
-------
Per taak: uit (handmatig), elke X uur, of dagelijks om een tijd. Zet bij
Instellingen aan dat sluiten naar het systeemvak gaat (en eventueel met Windows
meestarten), dan draaien geplande back-ups op de achtergrond door.

UITVOEREN
---------
Nu uitvoeren (gekozen taak) of Alle uitvoeren. Voortgang en meldingen staan in
het logboek onderaan; logs worden ook bewaard in DraveBackup-data\logs.

Snelgids: druk op F1. Losse .exe maken: bouw-exe.bat (onefile).

DONATIE (vrijwillig): https://paypal.me/roger076
CONTACT: service@dravenlock.nl
