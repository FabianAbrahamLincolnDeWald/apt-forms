# -*- coding: utf-8 -*-
"""Holt den Airbnb-iCal, schreibt bookings.json und zwei Kalender-Feeds."""
import os, json, datetime, urllib.request, hashlib

PFAD   = os.environ.get('PFAD', 'hgsnhbszcpvn08zk')
ANCHOR = os.environ.get('ANCHOR', '2026-09-05')
HORIZON = 120

# ---------- iCal einlesen ----------
raw = urllib.request.urlopen(os.environ['ICAL_URL'], timeout=30).read().decode('utf-8', 'replace')
raw = raw.replace('\r\n ', '').replace('\r\n', '\n')
events, cur = [], None
for line in raw.split('\n'):
    if line == 'BEGIN:VEVENT': cur = {}
    elif line == 'END:VEVENT':
        if cur: events.append(cur); cur = None
    elif cur is not None and ':' in line:
        k, v = line.split(':', 1); cur[k.split(';')[0]] = v.strip()

def iso(s): s = s[:8]; return '%s-%s-%s' % (s[:4], s[4:6], s[6:8])
res = [e for e in events if 'Reserved' in e.get('SUMMARY', '')] or events
cut = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
bookings = sorted([[iso(e['DTSTART']), iso(e['DTEND'])]
                   for e in res if 'DTSTART' in e and 'DTEND' in e and iso(e['DTEND']) >= cut])

# ---------- Reinigungsplan rechnen ----------
D = lambda s: datetime.date(*map(int, s.split('-')))
ins  = {D(a) for a, b in bookings}
outs = {D(b) for a, b in bookings}
occ  = set()
for a, b in bookings:
    x = D(a)
    while x < D(b): occ.add(x); x += datetime.timedelta(1)

plan, last = [], D(ANCHOR)
cur_d = last + datetime.timedelta(1)
for _ in range(HORIZON):
    gap = (cur_d - last).days
    t = None
    if cur_d in outs and cur_d in ins:      t = 'WECHSEL'
    elif cur_d in outs:                     t = 'AUSZUG'
    elif (cur_d + datetime.timedelta(1)) in ins and gap >= 2: t = 'VORBEREITUNG'
    elif gap >= 3:                          t = 'ZWISCHEN' if cur_d in occ else 'LEERSTAND'
    if t: plan.append((cur_d, t)); last = cur_d
    cur_d += datetime.timedelta(1)

VTIMEZONE = """BEGIN:VTIMEZONE
TZID:Atlantic/Madeira
BEGIN:DAYLIGHT
TZOFFSETFROM:+0000
TZOFFSETTO:+0100
TZNAME:WEST
DTSTART:19700329T010000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0100
TZOFFSETTO:+0000
TZNAME:WET
DTSTART:19701025T020000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE"""

# Zeitfenster je Einsatzart: Start (Ortszeit Madeira) und Dauer in Minuten
SLOT = {'WECHSEL':('10:00',240), 'AUSZUG':('10:00',180), 'VORBEREITUNG':('10:00',90),
        'ZWISCHEN':('11:30',90), 'LEERSTAND':('11:30',45),
        'IN':('14:00',15), 'OUT':('10:00',15)}

# ---------- Texte ----------
TXT = {
 'pt': {'WECHSEL':('Limpeza — mudança de hóspedes','Limpeza completa entre a saída e a entrada. Roupa de cama e toalhas trocadas, fotos antes e depois.'),
        'AUSZUG':('Limpeza — saída de hóspedes','Limpeza completa no dia da saída. A hora combina-se antes.'),
        'VORBEREITUNG':('Preparar o apartamento','Deixar tudo pronto para os hóspedes que chegam amanhã: cama feita, toalhas, consumíveis.'),
        'ZWISCHEN':('Limpeza — com hóspedes na casa','Refrescar: pó, cama esticada, casa de banho, arejar. Depois a entrada, o corredor e as escadas.'),
        'LEERSTAND':('Visita — apartamento vazio','Visita curta: arejar, verificar, e sobretudo a entrada, o corredor e as escadas do prédio.'),
        'IN':('Chegada de hóspedes',''), 'OUT':('Saída de hóspedes',''), 'NAME':'Limpezas — Apartamento'},
 'de': {'WECHSEL':('Reinigung — Gästewechsel','Komplette Reinigung zwischen Abreise und Anreise. Bettwäsche und Handtücher wechseln, Fotos vorher und nachher.'),
        'AUSZUG':('Reinigung — Abreisetag','Komplette Reinigung am Abreisetag. Uhrzeit wird vorher abgestimmt.'),
        'VORBEREITUNG':('Wohnung vorbereiten','Alles bereit machen für die Gäste, die morgen anreisen: Bett, Handtücher, Verbrauchsmaterial.'),
        'ZWISCHEN':('Reinigung — Gäste in der Wohnung','Auffrischen: Staub, Bett glatt ziehen, Bad, lüften. Danach Eingang, Flur und Treppen.'),
        'LEERSTAND':('Besuch — Wohnung leer','Kurzer Besuch: lüften, nachsehen, und vor allem Eingang, Flur und Treppenhaus.'),
        'IN':('Anreise Gäste',''), 'OUT':('Abreise Gäste',''), 'NAME':'Reinigung — Wohnung Funchal'},
}

def esc(s):
    return s.replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')

def ics(lang):
    T = TXT[lang]
    stamp = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    L = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Apartamento Funchal//Limpezas//DE',
         'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
         'X-WR-CALNAME:' + esc(T['NAME']), 'X-WR-TIMEZONE:Atlantic/Madeira',
         'REFRESH-INTERVAL;VALUE=DURATION:PT3H', 'X-PUBLISHED-TTL:PT3H']
    L.extend(VTIMEZONE.split('\n'))
    def ev(day, title, desc, tag):
        uid = hashlib.md5(('%s|%s|%s' % (day, tag, lang)).encode()).hexdigest() + '@funchal'
        hhmm, dur = SLOT[tag]
        h, m = map(int, hhmm.split(':'))
        st = datetime.datetime.combine(day, datetime.time(h, m))
        en = st + datetime.timedelta(minutes=dur)
        fmt = lambda x: x.strftime('%Y%m%dT%H%M%S')
        L.extend(['BEGIN:VEVENT', 'UID:' + uid, 'DTSTAMP:' + stamp,
                  'DTSTART;TZID=Atlantic/Madeira:' + fmt(st),
                  'DTEND;TZID=Atlantic/Madeira:' + fmt(en),
                  'SUMMARY:' + esc(title), 'TRANSP:OPAQUE'])
        if desc: L.append('DESCRIPTION:' + esc(desc))
        L.extend(['BEGIN:VALARM', 'ACTION:DISPLAY', 'DESCRIPTION:' + esc(title),
                  'TRIGGER:-PT12H', 'END:VALARM', 'END:VEVENT'])
    for day, t in plan:
        ev(day, T[t][0], T[t][1], t)
    for a, b in bookings:
        if D(a) >= datetime.date.today(): ev(D(a), T['IN'][0], '', 'IN')
        if D(b) >= datetime.date.today(): ev(D(b), T['OUT'][0], '', 'OUT')
    L.append('END:VCALENDAR')
    out = []
    for line in L:
        b = line.encode('utf-8')
        while len(b) > 73:
            cut = 73
            while cut > 0 and (b[cut] & 0xC0) == 0x80: cut -= 1
            out.append(b[:cut].decode('utf-8')); b = b' ' + b[cut:]
        out.append(b.decode('utf-8'))
    return '\r\n'.join(out) + '\r\n'

# ---------- schreiben ----------
def write(path, content):
    old = None
    if os.path.exists(path):
        old = open(path, 'rb').read().decode('utf-8')
    # Zeitstempel ausklammern, damit nicht jede Stunde ein Commit entsteht
    norm = lambda s: '\n'.join(l for l in s.split('\n') if not l.startswith(('DTSTAMP', ' "updated"')))
    if old is not None and norm(old) == norm(content):
        print('unverändert:', path); return False
    open(path, 'wb').write(content.encode('utf-8'))
    print('geschrieben:', path); return True

write(os.path.join(PFAD, 'bookings.json'),
      json.dumps({'updated': datetime.datetime.utcnow().isoformat(timespec='minutes') + 'Z',
                  'bookings': bookings}, indent=1, ensure_ascii=False))
write(os.path.join(PFAD, 'limpezas_pt.ics'), ics('pt'))
write(os.path.join(PFAD, 'limpezas_de.ics'), ics('de'))
print(len(bookings), 'Buchungen,', len(plan), 'Einsätze im Plan')
