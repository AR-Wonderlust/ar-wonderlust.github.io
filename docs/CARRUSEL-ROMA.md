# Carrusel ROMA para tablet y TV

Abrir https://ar-wonderlust.github.io/blog/ y tocar Pantalla completa. La función depende del navegador del dispositivo; si no la permite, la presentación continúa en la ventana. Usar flechas o botones para navegar, Pausar para detener. Duración aproximada: 3 minutos 21 segundos por vuelta. Las pantallas de QR permanecen 25–30 segundos. Con preferencia de movimiento reducido comienza pausado. El navegador pausa el avance cuando la pestaña está oculta o el foco está en un enlace del contenido.

Contenido editable: assets/showcase/slides.json. Estilos: showcase.css. Comportamiento: showcase.js. QR SVG locales, sin servicios externos de generación. Mantener borde blanco, alto contraste y comprobar con un teléfono a la distancia real de uso.

La presentación es estática e independiente del servidor local, pero necesita Internet para la carga inicial y para abrir redes. No implementa modo offline.

El QR de WhatsApp abre +54 9 388 538-3215 con ROMA-VIAJE; el pasajero debe tocar Enviar. No se ha activado ninguna respuesta automática. Cuando vuelva el servidor: implementar reconocimiento del mensaje, respuesta con Instagram y reseña de Agencia ROMA, deduplicación de mensajes y prueba real. Los QR directos a Instagram, TikTok y Google ya están incluidos.

Reseñas: https://g.page/r/CeDpsUjiSiCXEAE/review proviene del enlace existente en la web de Agencia ROMA. No se presenta como reseña de Casa ROMA Yala. El QR del flyer de Yala no pudo decodificarse; falta su URL exacta.

Fotos: Hornocal facilitado por el usuario; pileta de Casa ROMA del repositorio; imágenes de vehículos procedentes del material comercial facilitado, recortadas visualmente mediante SVG. Reemplazar por fotos originales de la flota cuando estén disponibles para mejorar definición. Se conservan las noticias en /blog/noticias/ y sus entradas originales.

Pruebas realizadas: sintaxis JavaScript, generación y decodificación de cuatro QR; navegación y pausa en navegador. Pantalla completa solicitada y rechazo controlado en el navegador de pruebas. Pendiente comprobar pantalla completa, lectura de QR a distancia y orientación en tablet/TV físicos.

Despliegue: el script entregado crea una rama nueva desde origin/main, conserva una rama backup/pre-showcase-FECHA, guarda un git archive del estado previo fuera del repositorio y verifica cambios antes de escribir. --prepare crea un commit local; --deploy también publica backup, rama y actualización de main mediante push normal sin force. Si GitHub rechaza main por protección, abrir PR desde la rama ya publicada.

Rollback: usar git revert sobre el commit del carrusel y publicar el revert. No resetear main ni forzar el push, para conservar otros cambios posteriores.
