"""Generate strings.json and translations/*.json from one table.

Every user-facing string lives here once, in the seven languages Plumio ships in.
Run:  python scripts/gen_translations.py
"""

from __future__ import annotations

import json
from pathlib import Path

LANGS = ["en", "es", "de", "fr", "it", "pt", "zh-Hant"]
OUT = Path(__file__).resolve().parent.parent / "custom_components" / "plumio"

# path -> [en, es, de, fr, it, pt, zh-Hant]
T: dict[str, list[str]] = {
    # ---------- config flow ----------
    "config.step.link.title": ["Link your Nest", "Enlaza tu Nido", "Nest verknüpfen", "Associer votre Nid", "Collega il tuo Nido", "Vincule seu Ninho", "連結你的巢"],
    "config.step.link.description": [
        "On the phone of the Nest's admin, scan this code with the camera, or open Plumio → Nest → Integrations and type:\n\n## {code}\n\nApprove it there, then press **Submit** here. The code is valid for 10 minutes.",
        "En el teléfono de quien administra el Nido, escanea este código con la cámara, o abre Plumio → Nido → Integraciones y escribe:\n\n## {code}\n\nApruébalo allí y luego pulsa **Enviar** aquí. El código vale 10 minutos.",
        "Scanne diesen Code mit der Kamera des Handys der Person, die das Nest verwaltet, oder öffne Plumio → Nest → Integrationen und gib ein:\n\n## {code}\n\nBestätige dort und drücke dann hier auf **Absenden**. Der Code gilt 10 Minuten.",
        "Sur le téléphone de l'administrateur du Nid, scannez ce code avec l'appareil photo, ou ouvrez Plumio → Nid → Intégrations et saisissez :\n\n## {code}\n\nApprouvez-le là-bas, puis appuyez sur **Envoyer** ici. Le code est valable 10 minutes.",
        "Sul telefono di chi amministra il Nido, scansiona questo codice con la fotocamera, oppure apri Plumio → Nido → Integrazioni e scrivi:\n\n## {code}\n\nApprovalo lì, poi premi **Invia** qui. Il codice vale 10 minuti.",
        "No telefone de quem administra o Ninho, escaneie este código com a câmera, ou abra Plumio → Ninho → Integrações e digite:\n\n## {code}\n\nAprove lá e depois toque em **Enviar** aqui. O código vale por 10 minutos.",
        "用巢管理員的手機相機掃描這個條碼，或開啟 Plumio → 巢 → 整合並輸入：\n\n## {code}\n\n在手機上核准後，再按這裡的**傳送**。代碼有效時間為 10 分鐘。",
    ],
    "config.step.link.data.qr": ["Scan with the admin's phone", "Escanéalo con el teléfono del admin", "Mit dem Handy des Admins scannen", "À scanner avec le téléphone de l'admin", "Scansiona con il telefono dell'admin", "Escaneie com o telefone do admin", "用管理員的手機掃描"],
    "config.error.cannot_connect": ["Could not reach Plumio. Check your connection and try again.", "No se pudo conectar con Plumio. Revisa tu conexión e inténtalo de nuevo.", "Plumio ist nicht erreichbar. Prüfe die Verbindung und versuche es erneut.", "Impossible de joindre Plumio. Vérifiez votre connexion et réessayez.", "Impossibile raggiungere Plumio. Controlla la connessione e riprova.", "Não foi possível conectar ao Plumio. Verifique sua conexão e tente de novo.", "無法連線到 Plumio。請檢查網路後再試一次。"],
    "config.error.not_approved_yet": ["Not approved yet. Approve it in the Plumio app, then press Submit again.", "Todavía no está aprobado. Apruébalo en la app de Plumio y pulsa Enviar otra vez.", "Noch nicht bestätigt. Bestätige in der Plumio-App und drücke erneut auf Absenden.", "Pas encore approuvé. Approuvez-le dans l'app Plumio, puis appuyez de nouveau sur Envoyer.", "Non ancora approvato. Approvalo nell'app Plumio e premi di nuovo Invia.", "Ainda não foi aprovado. Aprove no app do Plumio e toque em Enviar de novo.", "尚未核准。請在 Plumio App 中核准，然後再按一次傳送。"],
    "config.error.denied": ["The request was rejected in the app. Here is a new code.", "La solicitud se rechazó en la app. Aquí tienes un código nuevo.", "Die Anfrage wurde in der App abgelehnt. Hier ist ein neuer Code.", "La demande a été refusée dans l'app. Voici un nouveau code.", "La richiesta è stata rifiutata nell'app. Ecco un nuovo codice.", "O pedido foi recusado no app. Aqui está um novo código.", "請求已在 App 中被拒絕。這是新的代碼。"],
    "config.error.expired": ["That code expired. Here is a new one.", "Ese código caducó. Aquí tienes uno nuevo.", "Dieser Code ist abgelaufen. Hier ist ein neuer.", "Ce code a expiré. En voici un nouveau.", "Quel codice è scaduto. Eccone uno nuovo.", "Esse código expirou. Aqui está um novo.", "該代碼已過期。這是新的代碼。"],
    "config.abort.cannot_connect": ["Could not reach Plumio. Try again in a moment.", "No se pudo conectar con Plumio. Inténtalo de nuevo en un momento.", "Plumio ist nicht erreichbar. Versuche es gleich noch einmal.", "Impossible de joindre Plumio. Réessayez dans un instant.", "Impossibile raggiungere Plumio. Riprova tra poco.", "Não foi possível conectar ao Plumio. Tente de novo em instantes.", "無法連線到 Plumio。請稍後再試。"],
    "config.abort.already_configured": ["This Nest is already linked. The link you just approved is not used: disconnect it in the Plumio app (Nest → Integrations).", "Este Nido ya está enlazado. El enlace que acabas de aprobar no se usa: desconéctalo en la app de Plumio (Nido → Integraciones).", "Dieses Nest ist bereits verknüpft. Die gerade bestätigte Verknüpfung wird nicht verwendet: Trenne sie in der Plumio-App (Nest → Integrationen).", "Ce Nid est déjà associé. La liaison que vous venez d'approuver n'est pas utilisée : déconnectez-la dans l'app Plumio (Nid → Intégrations).", "Questo Nido è già collegato. Il collegamento appena approvato non viene usato: scollegalo nell'app Plumio (Nido → Integrazioni).", "Este Ninho já está vinculado. O vínculo que você acabou de aprovar não é usado: desconecte-o no app do Plumio (Ninho → Integrações).", "這個巢已經連結。你剛核准的連結不會被使用：請在 Plumio App（巢 → 整合）中中斷它。"],
    "config.abort.reauth_successful": ["Linked again.", "Enlazado de nuevo.", "Erneut verknüpft.", "Associé de nouveau.", "Collegato di nuovo.", "Vinculado de novo.", "已重新連結。"],
    "config.abort.wrong_nest": ["A different Nest was approved. Disconnect that link in the Plumio app (Nest → Integrations), then approve the same Nest that was linked before.", "Se aprobó un Nido distinto. Desconecta ese enlace en la app de Plumio (Nido → Integraciones) y aprueba el mismo Nido que estaba enlazado.", "Es wurde ein anderes Nest bestätigt. Trenne diese Verknüpfung in der Plumio-App (Nest → Integrationen) und bestätige dasselbe Nest wie zuvor.", "Un autre Nid a été approuvé. Déconnectez cette liaison dans l'app Plumio (Nid → Intégrations), puis approuvez le même Nid qu'auparavant.", "È stato approvato un Nido diverso. Scollega quel collegamento nell'app Plumio (Nido → Integrazioni), poi approva lo stesso Nido di prima.", "Outro Ninho foi aprovado. Desconecte esse vínculo no app do Plumio (Ninho → Integrações) e aprove o mesmo Ninho de antes.", "核准的是另一個巢。請在 Plumio App（巢 → 整合）中中斷那個連結，然後核准先前連結的同一個巢。"],
    # ---------- options ----------
    "options.step.init.title": ["Plumio options", "Opciones de Plumio", "Plumio-Optionen", "Options Plumio", "Opzioni Plumio", "Opções do Plumio", "Plumio 選項"],
    "options.step.init.data.home_from_places": ["Treat Plumio places of type Home as home", "Tratar los lugares de tipo Casa de Plumio como casa", "Plumio-Orte vom Typ Zuhause als Zuhause werten", "Considérer les lieux Plumio de type Maison comme domicile", "Considera casa i luoghi Plumio di tipo Casa", "Tratar lugares do Plumio do tipo Casa como casa", "將 Plumio 中類型為「家」的地點視為在家"],
    "options.step.init.data.max_gps_accuracy": ["Ignore fixes less precise than", "Ignorar ubicaciones menos precisas que", "Standorte ignorieren, die ungenauer sind als", "Ignorer les positions moins précises que", "Ignora le posizioni meno precise di", "Ignorar localizações menos precisas que", "忽略精確度低於此值的定位"],
    "options.step.init.data_description.max_gps_accuracy": ["0 accepts everything.", "0 lo acepta todo.", "0 akzeptiert alles.", "0 accepte tout.", "0 accetta tutto.", "0 aceita tudo.", "0 表示全部接受。"],
    "options.step.init.data.bermuda_auto_add": ["Add my tags to Bermuda automatically", "Añadir mis tags a Bermuda automáticamente", "Meine Tags automatisch zu Bermuda hinzufügen", "Ajouter mes tags à Bermuda automatiquement", "Aggiungi automaticamente i miei tag a Bermuda", "Adicionar meus tags ao Bermuda automaticamente", "自動將我的追蹤器加入 Bermuda"],
    "options.step.init.data_description.bermuda_auto_add": [
        "With Bluetooth proxies and the Bermuda integration, each tag gets the room it is in. This adds the Nest's tags to Bermuda's list of devices to track; it never removes anything.",
        "Con proxies Bluetooth y la integración Bermuda, cada tag sabe en qué habitación está. Esto añade los tags del Nido a la lista de dispositivos que sigue Bermuda; nunca quita nada.",
        "Mit Bluetooth-Proxys und der Bermuda-Integration bekommt jeder Tag den Raum, in dem er liegt. Das fügt die Tags des Nests zu Bermudas Geräteliste hinzu; entfernt wird nie etwas.",
        "Avec des proxys Bluetooth et l'intégration Bermuda, chaque tag connaît la pièce où il se trouve. Ceci ajoute les tags du Nid à la liste d'appareils suivis par Bermuda ; rien n'est jamais retiré.",
        "Con proxy Bluetooth e l'integrazione Bermuda, ogni tag sa in quale stanza si trova. Questo aggiunge i tag del Nido all'elenco dei dispositivi seguiti da Bermuda; non rimuove mai nulla.",
        "Com proxies Bluetooth e a integração Bermuda, cada tag sabe em que cômodo está. Isto adiciona os tags do Ninho à lista de dispositivos que o Bermuda acompanha; nunca remove nada.",
        "透過藍牙代理與 Bermuda 整合，每個追蹤器都能知道自己在哪個房間。這會把巢的追蹤器加入 Bermuda 的追蹤清單；不會移除任何東西。",
    ],
    "options.step.rooms.title": ["Room of each tag", "Habitación de cada tag", "Raum jedes Tags", "Pièce de chaque tag", "Stanza di ogni tag", "Cômodo de cada tag", "每個追蹤器的房間"],
    "options.step.rooms.description": [
        "Leave a tag empty to use Bermuda's Area sensor, found on its own. Or pick any sensor whose state is the name of a room (ESPresense, room-assistant, a template).",
        "Deja un tag vacío para usar el sensor Área de Bermuda, que se encuentra solo. O elige cualquier sensor cuyo estado sea el nombre de una habitación (ESPresense, room-assistant, una plantilla).",
        "Lass einen Tag leer, um Bermudas Bereichssensor zu verwenden, der automatisch gefunden wird. Oder wähle einen beliebigen Sensor, dessen Zustand der Name eines Raums ist (ESPresense, room-assistant, eine Vorlage).",
        "Laissez un tag vide pour utiliser le capteur Zone de Bermuda, trouvé automatiquement. Ou choisissez n'importe quel capteur dont l'état est le nom d'une pièce (ESPresense, room-assistant, un modèle).",
        "Lascia vuoto un tag per usare il sensore Area di Bermuda, trovato da solo. Oppure scegli un qualsiasi sensore il cui stato sia il nome di una stanza (ESPresense, room-assistant, un modello).",
        "Deixe um tag vazio para usar o sensor Área do Bermuda, encontrado sozinho. Ou escolha qualquer sensor cujo estado seja o nome de um cômodo (ESPresense, room-assistant, um modelo).",
        "留空即使用 Bermuda 的區域感測器（會自動找到）。或選擇任何狀態為房間名稱的感測器（ESPresense、room-assistant、範本）。",
    ],
    # ---------- sensors ----------
    "entity.sensor.battery.name": ["Battery", "Batería", "Akku", "Batterie", "Batteria", "Bateria", "電量"],
    "entity.sensor.speed.name": ["Speed", "Velocidad", "Geschwindigkeit", "Vitesse", "Velocità", "Velocidade", "速度"],
    "entity.sensor.activity.name": ["Activity", "Actividad", "Aktivität", "Activité", "Attività", "Atividade", "活動"],
    "entity.sensor.activity.state.still": ["Still", "Quieto", "Ruhend", "Immobile", "Fermo", "Parado", "靜止"],
    "entity.sensor.activity.state.walking": ["Walking", "Andando", "Zu Fuß", "À pied", "A piedi", "Andando", "步行"],
    "entity.sensor.activity.state.running": ["Running", "Corriendo", "Laufend", "En course", "Di corsa", "Correndo", "跑步"],
    "entity.sensor.activity.state.on_bicycle": ["Cycling", "En bici", "Mit dem Rad", "À vélo", "In bici", "De bicicleta", "騎單車"],
    "entity.sensor.activity.state.in_vehicle": ["In a vehicle", "En vehículo", "Im Fahrzeug", "En véhicule", "In veicolo", "Em veículo", "乘車"],
    "entity.sensor.activity.state.unknown": ["Unknown", "Desconocida", "Unbekannt", "Inconnue", "Sconosciuta", "Desconhecida", "未知"],
    "entity.sensor.place.name": ["Place", "Lugar", "Ort", "Lieu", "Luogo", "Lugar", "地點"],
    "entity.sensor.place_since.name": ["At place since", "En el lugar desde", "Am Ort seit", "Sur place depuis", "Nel luogo da", "No lugar desde", "抵達地點時間"],
    "entity.sensor.last_seen.name": ["Last seen", "Última vez visto", "Zuletzt gesehen", "Vu pour la dernière fois", "Ultimo accesso", "Visto por último", "上次上線"],
    "entity.sensor.location_updated.name": ["Location updated", "Ubicación actualizada", "Standort aktualisiert", "Position mise à jour", "Posizione aggiornata", "Localização atualizada", "位置更新時間"],
    "entity.sensor.heading.name": ["Heading", "Rumbo", "Richtung", "Cap", "Direzione", "Direção", "方向"],
    "entity.sensor.gps_accuracy.name": ["GPS accuracy", "Precisión GPS", "GPS-Genauigkeit", "Précision GPS", "Precisione GPS", "Precisão do GPS", "GPS 精確度"],
    "entity.sensor.distance_from_home.name": ["Distance from home", "Distancia a casa", "Entfernung von zu Hause", "Distance du domicile", "Distanza da casa", "Distância de casa", "離家距離"],
    "entity.sensor.last_trip_distance.name": ["Last trip distance", "Distancia del último viaje", "Strecke der letzten Fahrt", "Distance du dernier trajet", "Distanza dell'ultimo viaggio", "Distância da última viagem", "上次行程距離"],
    "entity.sensor.last_trip_max_speed.name": ["Last trip top speed", "Velocidad máxima del último viaje", "Höchsttempo der letzten Fahrt", "Vitesse max du dernier trajet", "Velocità massima dell'ultimo viaggio", "Velocidade máxima da última viagem", "上次行程最高速度"],
    "entity.sensor.last_trip_ended.name": ["Last trip ended", "Fin del último viaje", "Ende der letzten Fahrt", "Fin du dernier trajet", "Fine dell'ultimo viaggio", "Fim da última viagem", "上次行程結束時間"],
    "entity.sensor.last_trip_events.name": ["Last trip driving events", "Incidencias del último viaje", "Fahrereignisse der letzten Fahrt", "Événements du dernier trajet", "Eventi dell'ultimo viaggio", "Ocorrências da última viagem", "上次行程駕駛事件"],
    "entity.sensor.members_home.name": ["Members home", "Miembros en casa", "Mitglieder zu Hause", "Membres à la maison", "Membri a casa", "Membros em casa", "在家成員數"],
    "entity.sensor.plan.name": ["Plan", "Plan", "Tarif", "Forfait", "Piano", "Plano", "方案"],
    "entity.sensor.plan.state.free": ["Free", "Gratis", "Kostenlos", "Gratuit", "Gratuito", "Grátis", "免費"],
    "entity.sensor.plan.state.premium": ["Premium", "Premium", "Premium", "Premium", "Premium", "Premium", "Premium"],
    "entity.sensor.plan.state.paused": ["Paused", "En pausa", "Pausiert", "En pause", "In pausa", "Em pausa", "已暫停"],
    "entity.sensor.occupancy.name": ["Members here", "Miembros aquí", "Mitglieder hier", "Membres présents", "Membri presenti", "Membros aqui", "此處成員數"],
    "entity.sensor.tag_battery.name": ["Battery voltage", "Voltaje de la pila", "Batteriespannung", "Tension de la pile", "Tensione della batteria", "Tensão da bateria", "電池電壓"],
    "entity.sensor.tag_room.name": ["Room", "Habitación", "Raum", "Pièce", "Stanza", "Cômodo", "房間"],
    "entity.sensor.tag_last_seen.name": ["Last seen", "Última vez visto", "Zuletzt gesehen", "Vu pour la dernière fois", "Ultimo rilevamento", "Visto por último", "上次偵測時間"],
    # ---------- binary sensors ----------
    "entity.binary_sensor.charging.name": ["Charging", "Cargando", "Lädt", "En charge", "In carica", "Carregando", "充電中"],
    "entity.binary_sensor.online.name": ["Online", "En línea", "Online", "En ligne", "Online", "Online", "上線"],
    "entity.binary_sensor.driving.name": ["Driving", "Conduciendo", "Fährt", "En route", "In viaggio", "Dirigindo", "駕駛中"],
    "entity.binary_sensor.sharing.name": ["Sharing location", "Compartiendo ubicación", "Teilt Standort", "Partage sa position", "Condivide la posizione", "Compartilhando localização", "正在分享位置"],
    "entity.binary_sensor.approximate.name": ["Approximate area only", "Solo zona aproximada", "Nur ungefähre Zone", "Zone approximative seulement", "Solo zona approssimativa", "Só área aproximada", "僅大約區域"],
    "entity.binary_sensor.sos.name": ["SOS", "SOS", "SOS", "SOS", "SOS", "SOS", "緊急求救"],
    "entity.binary_sensor.security_alert.name": ["Security alert", "Alerta de seguridad", "Sicherheitswarnung", "Alerte de sécurité", "Avviso di sicurezza", "Alerta de segurança", "安全警示"],
    "entity.binary_sensor.not_reporting.name": ["Not reporting", "Sin reportar", "Meldet sich nicht", "Ne signale plus", "Non segnala", "Sem reportar", "未回報"],
    "entity.binary_sensor.live_connection.name": ["Live connection", "Conexión en vivo", "Live-Verbindung", "Connexion en direct", "Connessione in tempo reale", "Conexão ao vivo", "即時連線"],
    "entity.binary_sensor.anyone_home.name": ["Anyone home", "Alguien en casa", "Jemand zu Hause", "Quelqu'un à la maison", "Qualcuno a casa", "Alguém em casa", "有人在家"],
    "entity.binary_sensor.everyone_home.name": ["Everyone home", "Todos en casa", "Alle zu Hause", "Tout le monde à la maison", "Tutti a casa", "Todos em casa", "全員在家"],
    "entity.binary_sensor.occupied.name": ["Occupied", "Ocupado", "Belegt", "Occupé", "Occupato", "Ocupado", "有人"],
    # ---------- buttons ----------
    "entity.button.request_location.name": ["Request location", "Pedir ubicación", "Standort anfordern", "Demander la position", "Richiedi posizione", "Pedir localização", "要求更新位置"],
    "entity.button.ring.name": ["Ring phone", "Hacer sonar el teléfono", "Handy klingeln lassen", "Faire sonner le téléphone", "Fai squillare il telefono", "Tocar o telefone", "讓手機響鈴"],
    "entity.button.refresh_all.name": ["Refresh everyone", "Actualizar a todos", "Alle aktualisieren", "Actualiser tout le monde", "Aggiorna tutti", "Atualizar todos", "更新所有人"],
    # ---------- event entities ----------
    "entity.event.activity_events.name": ["Events", "Eventos", "Ereignisse", "Événements", "Eventi", "Eventos", "事件"],
    "entity.event.activity_events.state_attributes.event_type.state.arrival": ["Arrived", "Llegó", "Angekommen", "Arrivée", "Arrivo", "Chegou", "抵達"],
    "entity.event.activity_events.state_attributes.event_type.state.departure": ["Left", "Salió", "Gegangen", "Départ", "Partenza", "Saiu", "離開"],
    "entity.event.activity_events.state_attributes.event_type.state.checkin": ["Check-in", "Check-in", "Check-in", "Check-in", "Check-in", "Check-in", "報平安"],
    "entity.event.activity_events.state_attributes.event_type.state.sos": ["SOS", "SOS", "SOS", "SOS", "SOS", "SOS", "緊急求救"],
    "entity.event.activity_events.state_attributes.event_type.state.sos_resolved": ["SOS resolved", "SOS resuelto", "SOS beendet", "SOS résolu", "SOS risolto", "SOS resolvido", "求救已解除"],
    "entity.event.activity_events.state_attributes.event_type.state.crash": ["Crash detected", "Choque detectado", "Unfall erkannt", "Accident détecté", "Incidente rilevato", "Colisão detectada", "偵測到碰撞"],
    "entity.event.activity_events.state_attributes.event_type.state.speed_alert": ["Speeding", "Exceso de velocidad", "Zu schnell", "Excès de vitesse", "Eccesso di velocità", "Excesso de velocidade", "超速"],
    "entity.event.activity_events.state_attributes.event_type.state.low_battery": ["Low battery", "Batería baja", "Akku schwach", "Batterie faible", "Batteria scarica", "Bateria fraca", "電量偏低"],
    "entity.event.activity_events.state_attributes.event_type.state.trip_started": ["Trip started", "Viaje iniciado", "Fahrt begonnen", "Trajet commencé", "Viaggio iniziato", "Viagem iniciada", "行程開始"],
    "entity.event.activity_events.state_attributes.event_type.state.trip_ended": ["Trip ended", "Viaje terminado", "Fahrt beendet", "Trajet terminé", "Viaggio terminato", "Viagem encerrada", "行程結束"],
    "entity.event.activity_events.state_attributes.event_type.state.trip_completed": ["Trip summary", "Resumen del viaje", "Fahrtübersicht", "Résumé du trajet", "Riepilogo del viaggio", "Resumo da viagem", "行程摘要"],
    "entity.event.activity_events.state_attributes.event_type.state.security": ["Security alert", "Alerta de seguridad", "Sicherheitswarnung", "Alerte de sécurité", "Avviso di sicurezza", "Alerta de segurança", "安全警示"],
    "entity.event.activity_events.state_attributes.event_type.state.member_stale": ["Stopped reporting", "Dejó de reportar", "Meldet sich nicht mehr", "Ne signale plus", "Non segnala più", "Parou de reportar", "停止回報"],
    "entity.event.activity_events.state_attributes.event_type.state.member_back": ["Reporting again", "Volvió a reportar", "Meldet sich wieder", "Signale de nouveau", "Segnala di nuovo", "Voltou a reportar", "恢復回報"],
    "entity.event.nest_events.name": ["Tag events", "Eventos de tags", "Tag-Ereignisse", "Événements des tags", "Eventi dei tag", "Eventos de tags", "標籤事件"],
    "entity.event.nest_events.state_attributes.event_type.state.tag_seen": ["Tag seen", "Tag visto", "Tag gesehen", "Tag détecté", "Tag rilevato", "Tag visto", "偵測到標籤"],
    # ---------- selectors ----------
    "selector.place_type.options.home": ["Home", "Casa", "Zuhause", "Maison", "Casa", "Casa", "家"],
    "selector.place_type.options.work": ["Work", "Trabajo", "Arbeit", "Travail", "Lavoro", "Trabalho", "公司"],
    "selector.place_type.options.school": ["School", "Colegio", "Schule", "École", "Scuola", "Escola", "學校"],
    "selector.place_type.options.custom": ["Other", "Otro", "Sonstiges", "Autre", "Altro", "Outro", "其他"],
    # ---------- exceptions ----------
    "exceptions.premium_required.message": ["This needs Plumio Premium on the Nest owner's account.", "Esto necesita Plumio Premium en la cuenta del dueño del Nido.", "Dafür braucht der Besitzer des Nests Plumio Premium.", "Cela nécessite Plumio Premium sur le compte du propriétaire du Nid.", "Serve Plumio Premium sull'account del proprietario del Nido.", "Isso precisa do Plumio Premium na conta do dono do Ninho.", "此功能需要巢擁有者訂閱 Plumio Premium。"],
    "issues.premium_locked.title": ["{nest}: unlock the map with Plumio Premium", "{nest}: desbloquea el mapa con Plumio Premium", "{nest}: Karte mit Plumio Premium freischalten", "{nest} : débloquez la carte avec Plumio Premium", "{nest}: sblocca la mappa con Plumio Premium", "{nest}: desbloqueie o mapa com o Plumio Premium", "{nest}：使用 Plumio Premium 解鎖地圖"],
    "issues.premium_locked.description": [
        "This Nest is on the free plan. Home Assistant gets who is home, which place each person is in, arrivals and departures, battery and SOS.\n\nWith Plumio Premium on the Nest owner's account it also gets each person's live position on the map, speed and activity, driving, trips, tags, and the actions: request a location, ring a phone and manage places. Those entities are already here, shown as unavailable.",
        "Este Nido está en el plan gratis. Home Assistant recibe quién está en casa, en qué lugar está cada persona, llegadas y salidas, batería y SOS.\n\nCon Plumio Premium en la cuenta del dueño del Nido recibe además la posición en vivo de cada persona en el mapa, velocidad y actividad, conducción, recorridos, tags y las acciones: pedir ubicación, hacer sonar un teléfono y gestionar lugares. Esas entidades ya están aquí, como no disponibles.",
        "Dieses Nest nutzt den kostenlosen Tarif. Home Assistant erfährt, wer zu Hause ist, an welchem Ort sich jede Person befindet, Ankünfte und Abfahrten, Akkustand und SOS.\n\nMit Plumio Premium auf dem Konto des Nest-Besitzers kommen die Live-Position jeder Person auf der Karte, Geschwindigkeit und Aktivität, Fahren, Fahrten, Tags und die Aktionen hinzu: Standort anfordern, ein Telefon klingeln lassen und Orte verwalten. Diese Entitäten sind bereits hier, als nicht verfügbar.",
        "Ce Nid utilise l'offre gratuite. Home Assistant sait qui est à la maison, dans quel lieu se trouve chaque personne, les arrivées et départs, la batterie et les SOS.\n\nAvec Plumio Premium sur le compte du propriétaire du Nid, il reçoit aussi la position en direct de chaque personne sur la carte, la vitesse et l'activité, la conduite, les trajets, les tags et les actions : demander une position, faire sonner un téléphone et gérer les lieux. Ces entités sont déjà là, indisponibles.",
        "Questo Nido usa il piano gratuito. Home Assistant sa chi è a casa, in quale luogo si trova ogni persona, arrivi e partenze, batteria e SOS.\n\nCon Plumio Premium sull'account del proprietario del Nido riceve anche la posizione in tempo reale di ogni persona sulla mappa, velocità e attività, guida, viaggi, tag e le azioni: richiedere la posizione, far squillare un telefono e gestire i luoghi. Quelle entità sono già qui, non disponibili.",
        "Este Ninho está no plano gratuito. O Home Assistant recebe quem está em casa, em que lugar cada pessoa está, chegadas e saídas, bateria e SOS.\n\nCom o Plumio Premium na conta do dono do Ninho ele recebe também a posição ao vivo de cada pessoa no mapa, velocidade e atividade, condução, viagens, tags e as ações: pedir a localização, fazer um telefone tocar e gerenciar lugares. Essas entidades já estão aqui, como indisponíveis.",
        "此巢使用免費方案。Home Assistant 會收到誰在家、每個人在哪個地點、抵達與離開、電量以及 SOS。\n\n巢擁有者訂閱 Plumio Premium 後，還會收到每個人在地圖上的即時位置、速度與活動、駕駛狀態、行程、追蹤器，以及各項操作：請求位置、讓手機響鈴與管理地點。這些實體已經在這裡，顯示為無法使用。",
    ],
    "exceptions.actions_disabled.message": ["The Nest's admin turned off actions for this integration in the Plumio app.", "Quien administra el Nido desactivó las acciones para esta integración en la app de Plumio.", "Der Admin des Nests hat Aktionen für diese Integration in der Plumio-App deaktiviert.", "L'administrateur du Nid a désactivé les actions pour cette intégration dans l'app Plumio.", "L'amministratore del Nido ha disattivato le azioni per questa integrazione nell'app Plumio.", "O administrador do Ninho desativou as ações desta integração no app do Plumio.", "巢管理員已在 Plumio App 中停用此整合的操作功能。"],
    "exceptions.rate_limited.message": ["Too soon. Wait a moment and try again.", "Demasiado pronto. Espera un momento e inténtalo de nuevo.", "Zu früh. Warte kurz und versuche es erneut.", "Trop tôt. Patientez un instant et réessayez.", "Troppo presto. Attendi un momento e riprova.", "Cedo demais. Espere um instante e tente de novo.", "操作太頻繁。請稍候再試。"],
    "exceptions.not_found.message": ["Plumio no longer knows that member or place.", "Plumio ya no conoce a ese miembro o lugar.", "Plumio kennt dieses Mitglied oder diesen Ort nicht mehr.", "Plumio ne connaît plus ce membre ou ce lieu.", "Plumio non conosce più quel membro o luogo.", "O Plumio não conhece mais esse membro ou lugar.", "Plumio 中已找不到該成員或地點。"],
    "exceptions.zone_limit.message": ["The Nest has reached its place limit: {detail}", "El Nido llegó a su límite de lugares: {detail}", "Das Nest hat sein Orte-Limit erreicht: {detail}", "Le Nid a atteint sa limite de lieux : {detail}", "Il Nido ha raggiunto il limite di luoghi: {detail}", "O Ninho atingiu o limite de lugares: {detail}", "巢的地點數量已達上限：{detail}"],
    "exceptions.validation_error.message": ["Plumio rejected the data: {detail}", "Plumio rechazó los datos: {detail}", "Plumio hat die Daten abgelehnt: {detail}", "Plumio a refusé les données : {detail}", "Plumio ha rifiutato i dati: {detail}", "O Plumio recusou os dados: {detail}", "Plumio 拒絕了這些資料：{detail}"],
    "exceptions.request_failed.message": ["Plumio refused the request: {detail}", "Plumio rechazó la petición: {detail}", "Plumio hat die Anfrage abgelehnt: {detail}", "Plumio a refusé la demande : {detail}", "Plumio ha rifiutato la richiesta: {detail}", "O Plumio recusou o pedido: {detail}", "Plumio 拒絕了請求：{detail}"],
    "exceptions.link_revoked.message": ["This Nest is no longer linked. Link it again from the integration page.", "Este Nido ya no está enlazado. Enlázalo de nuevo desde la página de la integración.", "Dieses Nest ist nicht mehr verknüpft. Verknüpfe es auf der Integrationsseite erneut.", "Ce Nid n'est plus associé. Associez-le de nouveau depuis la page de l'intégration.", "Questo Nido non è più collegato. Collegalo di nuovo dalla pagina dell'integrazione.", "Este Ninho não está mais vinculado. Vincule de novo na página da integração.", "這個巢已不再連結。請從整合頁面重新連結。"],
    "exceptions.cannot_connect.message": ["Could not reach Plumio.", "No se pudo conectar con Plumio.", "Plumio ist nicht erreichbar.", "Impossible de joindre Plumio.", "Impossibile raggiungere Plumio.", "Não foi possível conectar ao Plumio.", "無法連線到 Plumio。"],
    "exceptions.location_not_requested.message": ["Nothing was sent: this member paused sharing, was asked seconds ago, or has no phone to reach.", "No se envió nada: este miembro pausó el compartir, se le pidió hace segundos o no tiene teléfono al que llegar.", "Nichts gesendet: Dieses Mitglied teilt gerade nicht, wurde eben erst gefragt oder hat kein erreichbares Handy.", "Rien n'a été envoyé : ce membre a mis le partage en pause, vient d'être sollicité ou n'a pas de téléphone joignable.", "Non è stato inviato nulla: questo membro ha messo in pausa la condivisione, è stato appena interpellato o non ha un telefono raggiungibile.", "Nada foi enviado: este membro pausou o compartilhamento, foi consultado há segundos ou não tem telefone alcançável.", "未送出任何請求：該成員已暫停分享、剛剛才被要求過，或沒有可聯絡的手機。"],
    "exceptions.nest_not_found.message": ["That Nest is not linked or not loaded.", "Ese Nido no está enlazado o no está cargado.", "Dieses Nest ist nicht verknüpft oder nicht geladen.", "Ce Nid n'est pas associé ou pas chargé.", "Quel Nido non è collegato o non è caricato.", "Esse Ninho não está vinculado ou não foi carregado.", "該巢尚未連結或未載入。"],
    "exceptions.nest_ambiguous.message": ["More than one Nest is linked: say which one.", "Hay más de un Nido enlazado: indica cuál.", "Mehrere Nester sind verknüpft: Gib an, welches.", "Plusieurs Nids sont associés : précisez lequel.", "Ci sono più Nidi collegati: indica quale.", "Há mais de um Ninho vinculado: indique qual.", "已連結多個巢：請指定其中一個。"],
    "exceptions.member_not_found.message": ["That device is not a Plumio member.", "Ese dispositivo no es un miembro de Plumio.", "Dieses Gerät ist kein Plumio-Mitglied.", "Cet appareil n'est pas un membre Plumio.", "Quel dispositivo non è un membro Plumio.", "Esse dispositivo não é um membro do Plumio.", "該裝置不是 Plumio 成員。"],
}

# Shared field texts, reused by several services.
F_MEMBER = ["Member", "Miembro", "Mitglied", "Membre", "Membro", "Membro", "成員"]
F_MEMBER_D = ["The member's device.", "El dispositivo del miembro.", "Das Gerät des Mitglieds.", "L'appareil du membre.", "Il dispositivo del membro.", "O dispositivo do membro.", "該成員的裝置。"]
F_NEST = ["Nest", "Nido", "Nest", "Nid", "Nido", "Ninho", "巢"]
F_NEST_D = ["Only needed with more than one linked Nest.", "Solo hace falta con más de un Nido enlazado.", "Nur bei mehr als einem verknüpften Nest nötig.", "Nécessaire seulement avec plusieurs Nids associés.", "Serve solo con più Nidi collegati.", "Só é necessário com mais de um Ninho vinculado.", "只有連結多個巢時才需要。"]
F_NAME = ["Name", "Nombre", "Name", "Nom", "Nome", "Nome", "名稱"]
F_NAME_D = ["How the place is called.", "Cómo se llama el lugar.", "Wie der Ort heißt.", "Le nom du lieu.", "Come si chiama il luogo.", "Como o lugar se chama.", "地點的名稱。"]
F_LAT = ["Latitude", "Latitud", "Breitengrad", "Latitude", "Latitudine", "Latitude", "緯度"]
F_LAT_D = ["Latitude of the centre.", "Latitud del centro.", "Breitengrad des Mittelpunkts.", "Latitude du centre.", "Latitudine del centro.", "Latitude do centro.", "中心點的緯度。"]
F_LNG = ["Longitude", "Longitud", "Längengrad", "Longitude", "Longitudine", "Longitude", "經度"]
F_LNG_D = ["Longitude of the centre.", "Longitud del centro.", "Längengrad des Mittelpunkts.", "Longitude du centre.", "Longitudine del centro.", "Longitude do centro.", "中心點的經度。"]
F_RADIUS = ["Radius", "Radio", "Radius", "Rayon", "Raggio", "Raio", "半徑"]
F_RADIUS_D = ["Radius in metres.", "Radio en metros.", "Radius in Metern.", "Rayon en mètres.", "Raggio in metri.", "Raio em metros.", "半徑（公尺）。"]
F_TYPE = ["Type", "Tipo", "Typ", "Type", "Tipo", "Tipo", "類型"]
F_TYPE_D = ["What kind of place it is.", "Qué clase de lugar es.", "Welche Art von Ort es ist.", "Le genre de lieu.", "Che tipo di luogo è.", "Que tipo de lugar é.", "地點的種類。"]
F_PLACE = ["Place ID", "ID del lugar", "Orts-ID", "ID du lieu", "ID del luogo", "ID do lugar", "地點 ID"]
F_PLACE_D = ["The place's Plumio ID (the last part of its device identifier).", "El ID del lugar en Plumio (la última parte del identificador de su dispositivo).", "Die Plumio-ID des Orts (der letzte Teil seiner Gerätekennung).", "L'ID Plumio du lieu (la dernière partie de l'identifiant de son appareil).", "L'ID Plumio del luogo (l'ultima parte dell'identificatore del dispositivo).", "O ID do lugar no Plumio (a última parte do identificador do dispositivo).", "該地點的 Plumio ID（裝置識別碼的最後一段）。"]

SERVICES: dict[str, tuple[list[str], list[str], dict[str, tuple[list[str], list[str]]]]] = {
    "request_location": (
        ["Request location", "Pedir ubicación", "Standort anfordern", "Demander la position", "Richiedi posizione", "Pedir localização", "要求更新位置"],
        ["Wakes a member's phone to report a fresh location.", "Despierta el teléfono de un miembro para que reporte una ubicación reciente.", "Weckt das Handy eines Mitglieds, damit es einen frischen Standort meldet.", "Réveille le téléphone d'un membre pour qu'il envoie une position récente.", "Risveglia il telefono di un membro perché invii una posizione aggiornata.", "Acorda o telefone de um membro para enviar uma localização recente.", "喚醒成員的手機以回報最新位置。"],
        {"device_id": (F_MEMBER, F_MEMBER_D)},
    ),
    "ring_phone": (
        ["Ring phone", "Hacer sonar el teléfono", "Handy klingeln lassen", "Faire sonner le téléphone", "Fai squillare il telefono", "Tocar o telefone", "讓手機響鈴"],
        ["Makes a member's phone ring so it can be found.", "Hace sonar el teléfono de un miembro para encontrarlo.", "Lässt das Handy eines Mitglieds klingeln, um es zu finden.", "Fait sonner le téléphone d'un membre pour le retrouver.", "Fa squillare il telefono di un membro per trovarlo.", "Faz o telefone de um membro tocar para encontrá-lo.", "讓成員的手機響鈴以便尋找。"],
        {"device_id": (F_MEMBER, F_MEMBER_D)},
    ),
    "stop_ring": (
        ["Stop ringing", "Dejar de sonar", "Klingeln beenden", "Arrêter la sonnerie", "Ferma lo squillo", "Parar de tocar", "停止響鈴"],
        ["Stops a phone that is ringing.", "Detiene un teléfono que está sonando.", "Beendet das Klingeln eines Handys.", "Arrête un téléphone qui sonne.", "Ferma un telefono che sta squillando.", "Para um telefone que está tocando.", "停止正在響鈴的手機。"],
        {"device_id": (F_MEMBER, F_MEMBER_D)},
    ),
    "create_place": (
        ["Create place", "Crear lugar", "Ort erstellen", "Créer un lieu", "Crea luogo", "Criar lugar", "建立地點"],
        ["Adds a place to the Nest.", "Añade un lugar al Nido.", "Fügt dem Nest einen Ort hinzu.", "Ajoute un lieu au Nid.", "Aggiunge un luogo al Nido.", "Adiciona um lugar ao Ninho.", "在巢中新增地點。"],
        {"config_entry_id": (F_NEST, F_NEST_D), "name": (F_NAME, F_NAME_D), "latitude": (F_LAT, F_LAT_D), "longitude": (F_LNG, F_LNG_D), "radius": (F_RADIUS, F_RADIUS_D), "place_type": (F_TYPE, F_TYPE_D)},
    ),
    "update_place": (
        ["Update place", "Editar lugar", "Ort bearbeiten", "Modifier un lieu", "Modifica luogo", "Editar lugar", "編輯地點"],
        ["Changes a place of the Nest.", "Cambia un lugar del Nido.", "Ändert einen Ort des Nests.", "Modifie un lieu du Nid.", "Modifica un luogo del Nido.", "Altera um lugar do Ninho.", "修改巢中的地點。"],
        {"config_entry_id": (F_NEST, F_NEST_D), "place_id": (F_PLACE, F_PLACE_D), "name": (F_NAME, F_NAME_D), "latitude": (F_LAT, F_LAT_D), "longitude": (F_LNG, F_LNG_D), "radius": (F_RADIUS, F_RADIUS_D), "place_type": (F_TYPE, F_TYPE_D)},
    ),
    "delete_place": (
        ["Delete place", "Borrar lugar", "Ort löschen", "Supprimer un lieu", "Elimina luogo", "Excluir lugar", "刪除地點"],
        ["Removes a place from the Nest.", "Quita un lugar del Nido.", "Entfernt einen Ort aus dem Nest.", "Retire un lieu du Nid.", "Rimuove un luogo dal Nido.", "Remove um lugar do Ninho.", "從巢中移除地點。"],
        {"config_entry_id": (F_NEST, F_NEST_D), "place_id": (F_PLACE, F_PLACE_D)},
    ),
    "import_zones": (
        ["Import zones", "Importar zonas", "Zonen importieren", "Importer les zones", "Importa zone", "Importar zonas", "匯入區域"],
        ["Copies your Home Assistant zones into the Nest as places, skipping names it already has.", "Copia tus zonas de Home Assistant al Nido como lugares, saltando los nombres que ya tiene.", "Kopiert deine Home-Assistant-Zonen als Orte ins Nest und überspringt vorhandene Namen.", "Copie vos zones Home Assistant dans le Nid comme lieux, en ignorant les noms déjà présents.", "Copia le tue zone di Home Assistant nel Nido come luoghi, saltando i nomi già presenti.", "Copia suas zonas do Home Assistant para o Ninho como lugares, pulando nomes que já existem.", "將 Home Assistant 的區域複製到巢中成為地點，並略過已有的名稱。"],
        {"config_entry_id": (F_NEST, F_NEST_D)},
    ),
    "get_trips": (
        ["Get trips", "Obtener viajes", "Fahrten abrufen", "Obtenir les trajets", "Ottieni viaggi", "Obter viagens", "取得行程"],
        ["Returns a member's recent trips.", "Devuelve los viajes recientes de un miembro.", "Gibt die letzten Fahrten eines Mitglieds zurück.", "Renvoie les trajets récents d'un membre.", "Restituisce i viaggi recenti di un membro.", "Retorna as viagens recentes de um membro.", "傳回成員最近的行程。"],
        {"device_id": (F_MEMBER, F_MEMBER_D), "limit": (["Limit", "Límite", "Limit", "Limite", "Limite", "Limite", "數量上限"], ["How many trips to return.", "Cuántos viajes devolver.", "Wie viele Fahrten zurückgegeben werden.", "Combien de trajets renvoyer.", "Quanti viaggi restituire.", "Quantas viagens retornar.", "要傳回的行程數量。"])},
    ),
    "get_driving_summary": (
        ["Get driving summary", "Obtener resumen de conducción", "Fahrübersicht abrufen", "Obtenir le résumé de conduite", "Ottieni riepilogo di guida", "Obter resumo de direção", "取得駕駛摘要"],
        ["Returns a member's driving summary by period.", "Devuelve el resumen de conducción de un miembro por periodos.", "Gibt die Fahrübersicht eines Mitglieds nach Zeitraum zurück.", "Renvoie le résumé de conduite d'un membre par période.", "Restituisce il riepilogo di guida di un membro per periodo.", "Retorna o resumo de direção de um membro por período.", "依期間傳回成員的駕駛摘要。"],
        {"device_id": (F_MEMBER, F_MEMBER_D)},
    ),
    "get_day_timeline": (
        ["Get day timeline", "Obtener línea del día", "Tagesverlauf abrufen", "Obtenir la chronologie du jour", "Ottieni cronologia del giorno", "Obter linha do tempo do dia", "取得當日時間軸"],
        ["Returns a member's route, legs and stays for one day.", "Devuelve la ruta, los tramos y las estancias de un miembro en un día.", "Gibt Route, Abschnitte und Aufenthalte eines Mitglieds für einen Tag zurück.", "Renvoie l'itinéraire, les étapes et les séjours d'un membre pour une journée.", "Restituisce percorso, tratte e soste di un membro in un giorno.", "Retorna a rota, os trechos e as estadias de um membro em um dia.", "傳回成員某一天的路線、路段與停留。"],
        {"device_id": (F_MEMBER, F_MEMBER_D), "date": (["Date", "Fecha", "Datum", "Date", "Data", "Data", "日期"], ["The day to return. Today if omitted.", "El día a devolver. Hoy si se omite.", "Der gewünschte Tag. Ohne Angabe heute.", "Le jour à renvoyer. Aujourd'hui par défaut.", "Il giorno da restituire. Oggi se omesso.", "O dia a retornar. Hoje, se omitido.", "要查詢的日期，未填則為今天。"])},
    ),
}


def put(tree: dict, path: str, value: str) -> None:
    *parents, leaf = path.split(".")
    for key in parents:
        tree = tree.setdefault(key, {})
    tree[leaf] = value


def build(index: int) -> dict:
    tree: dict = {}
    for path, texts in T.items():
        put(tree, path, texts[index])
    for service, (name, description, fields) in SERVICES.items():
        put(tree, f"services.{service}.name", name[index])
        put(tree, f"services.{service}.description", description[index])
        for field, (field_name, field_description) in fields.items():
            put(tree, f"services.{service}.fields.{field}.name", field_name[index])
            put(tree, f"services.{service}.fields.{field}.description", field_description[index])
    return tree


def main() -> None:
    for path, texts in T.items():
        assert len(texts) == len(LANGS), path
    (OUT / "translations").mkdir(exist_ok=True)
    for index, lang in enumerate(LANGS):
        text = json.dumps(build(index), ensure_ascii=False, indent=2) + "\n"
        (OUT / "translations" / f"{lang}.json").write_text(text, encoding="utf-8")
        if lang == "en":
            (OUT / "strings.json").write_text(text, encoding="utf-8")
        if lang == "pt":
            # Home Assistant keeps Brazilian Portuguese apart; Plumio ships one Portuguese.
            (OUT / "translations" / "pt-BR.json").write_text(text, encoding="utf-8")
    print(f"{len(T)} strings + {len(SERVICES)} services x {len(LANGS)} languages")


if __name__ == "__main__":
    main()
