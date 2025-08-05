# 🤖 Agente de Marketing Automático

Un agente inteligente que analiza la competencia en redes sociales y genera contenido automáticamente para Facebook e Instagram.

## 📋 Características

- **🔍 Análisis de Competencia**: Scraping automático de páginas públicas de Facebook e Instagram
- **🧠 Inteligencia Artificial**: Generación de contenido mejorado usando OpenAI GPT
- **📊 Análisis de Patrones**: Extracción de hashtags, temas y patrones de éxito
- **🤖 Publicación Automática**: Publicación programada en Facebook (1 vez/día) e Instagram (3 veces/día)
- **⏰ Programación Inteligente**: Tareas automáticas con horarios optimizados
- **📈 Monitoreo**: Sistema completo de logging y alertas
- **🔧 Configuración Flexible**: Gestión segura de credenciales y configuraciones

## 🎯 Funcionalidades Principales

### 1. Análisis de Competencia
- Lee lista de competidores desde archivo Excel
- Extrae 3 últimas publicaciones de cada competidor
- Analiza fotos, videos, texto y hashtags
- Identifica patrones de éxito y tendencias

### 2. Generación de Contenido
- Utiliza IA (OpenAI GPT) para crear contenido mejorado
- Aplica insights de la competencia
- Mantiene voz de marca consistente
- Genera hashtags optimizados

### 3. Publicación Automática
- Facebook: 1 publicación diaria a hora programada
- Instagram: 3 publicaciones diarias (mañana, tarde, noche)
- Manejo automático de imágenes y formatos
- Sistema de reintentos en caso de errores

### 4. Monitoreo y Alertas
- Logging detallado de todas las operaciones
- Métricas de sistema en tiempo real
- Alertas automáticas por email/webhook
- Dashboard de estado del agente

## 🚀 Instalación

### Requisitos Previos

- Python 3.8 o superior
- Google Chrome (para scraping web)
- Cuentas de Facebook e Instagram para publicación
- API Key de OpenAI

### 1. Clonar Repositorio

```bash
git clone <repository-url>
cd marketing-agent
```

### 2. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 3. Configuración Inicial

```bash
python main.py --setup
```

Este comando creará:
- `config/agent_config.yaml`: Configuración principal
- `.env`: Variables de entorno (credenciales)
- `data/competidores.xlsx`: Plantilla Excel para competidores

### 4. Configurar Credenciales

Edita el archivo `.env` y completa las siguientes variables:

```env
# OpenAI API (Requerido)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Facebook API (Opcional)
FACEBOOK_ACCESS_TOKEN=your-facebook-access-token
FACEBOOK_PAGE_ID=your-facebook-page-id
FACEBOOK_APP_ID=your-facebook-app-id
FACEBOOK_APP_SECRET=your-facebook-app-secret
FACEBOOK_POST_TIME=09:00

# Instagram (Opcional)
INSTAGRAM_USERNAME=your-instagram-username
INSTAGRAM_PASSWORD=your-instagram-password
INSTAGRAM_POST_TIMES=09:00,14:00,19:00

# Configuración
BRAND_VOICE=profesional_y_amigable
TARGET_AUDIENCE=jovenes_adultos_25_45
```

### 5. Configurar Competidores

Edita `data/competidores.xlsx` y agrega:
- Nombre del competidor
- URL de Facebook
- URL de Instagram
- Sector/categoría
- Estado (Activo/Inactivo)

## 🎮 Uso

### Modo Interactivo (Recomendado para pruebas)

```bash
python main.py
```

Comandos disponibles:
- `status` - Ver estado del agente
- `tasks` - Listar tareas programadas
- `run <task_id>` - Ejecutar tarea manualmente
- `alerts` - Ver alertas activas
- `help` - Mostrar ayuda
- `quit` - Salir

### Modo Daemon (Producción)

```bash
python main.py --daemon
```

El agente se ejecutará en segundo plano siguiendo la programación automática.

### Verificar Sistema

```bash
python main.py --test
```

Verifica que todos los componentes estén configurados correctamente.

## 📊 Programación de Tareas

El agente ejecuta las siguientes tareas automáticamente:

| Tarea | Frecuencia | Hora | Descripción |
|-------|------------|------|-------------|
| Scraping | Cada 2 horas | :00 | Analiza competencia |
| Análisis | Diario | 08:30 | Procesa datos extraídos |
| Generación | Diario | 09:00 | Crea contenido nuevo |
| Facebook | Diario | 09:00* | Publica en Facebook |
| Instagram | 3x/día | 09:00, 14:00, 19:00* | Publica en Instagram |

*Horarios configurables en `.env`

## 📁 Estructura del Proyecto

```
marketing-agent/
├── main.py                 # Aplicación principal
├── requirements.txt        # Dependencias
├── .env.example           # Ejemplo de variables de entorno
├── README.md              # Este archivo
├── src/                   # Código fuente
│   ├── config_manager.py  # Gestión de configuración
│   ├── excel_reader.py    # Lectura de competidores
│   ├── social_scraper.py  # Scraping de redes sociales
│   ├── content_analyzer.py # Análisis de contenido
│   ├── content_generator.py # Generación con IA
│   ├── social_publisher.py # Publicación automática
│   ├── scheduler.py       # Programador de tareas
│   └── monitoring.py      # Monitoreo y logging
├── config/                # Configuraciones
│   ├── agent_config.yaml  # Configuración principal
│   └── credentials.enc    # Credenciales encriptadas
├── data/                  # Datos del agente
│   ├── competidores.xlsx  # Lista de competidores
│   ├── *.db              # Bases de datos SQLite
│   └── *.json            # Resultados de análisis
├── logs/                  # Archivos de log
├── media_storage/         # Contenido multimedia
└── generated_content/     # Contenido generado
```

## ⚙️ Configuración Avanzada

### Personalizar Horarios

Edita `config/agent_config.yaml`:

```yaml
facebook:
  post_time: "10:30"

instagram:
  post_times: ["08:00", "13:00", "20:00"]
```

### Configurar Voz de Marca

```yaml
ai:
  brand_voice: "casual_y_divertido"
  target_audience: "millennials_tech"
  temperature: 0.8
```

### Alertas por Email

```python
# En el código, configurar callback de email
email_callback = create_email_alert_callback(
    smtp_server="smtp.gmail.com",
    smtp_port=587,
    username="tu_email@gmail.com",
    password="tu_password",
    recipients=["admin@empresa.com"]
)
monitoring.register_alert_callback(email_callback)
```

## 🔒 Seguridad

- Las credenciales se almacenan encriptadas en `config/credentials.enc`
- La clave de encriptación se genera automáticamente
- Las APIs de redes sociales usan tokens seguros
- Logs no contienen información sensible

## 📈 Monitoreo

### Métricas Disponibles
- Uso de CPU, memoria y disco
- Tareas exitosas/fallidas
- Tiempo de respuesta de APIs
- Estado de health checks

### Logs
- `logs/marketing_agent.log`: Log principal
- `logs/errors.log`: Solo errores
- `logs/metrics.log`: Métricas del sistema

### Alertas
- Recursos del sistema altos
- Errores en APIs de redes sociales
- Fallos en tareas programadas
- Problemas de conectividad

## ❗ Solución de Problemas

### Error: "OpenAI API key es requerida"
**Solución**: Configurar `OPENAI_API_KEY` en `.env`

### Error: "No se encontraron competidores"
**Solución**: Verificar que `data/competidores.xlsx` tenga datos válidos

### Error: "API de Facebook no configurada"
**Solución**: 
1. Crear app en Facebook Developers
2. Obtener access token y page ID
3. Configurar en `.env`

### Error: "ChromeDriver not found"
**Solución**: 
```bash
# Ubuntu/Debian
sudo apt-get install google-chrome-stable

# MacOS
brew install chromedriver
```

### Instagram no funciona
**Solución**: 
1. Verificar username/password
2. Comprobar que la cuenta no tenga 2FA
3. Usar cuenta business si es posible

## 🔄 Actualizaciones

Para actualizar el agente:

```bash
git pull origin main
pip install -r requirements.txt --upgrade
python main.py --test
```

## 📞 Soporte

### Logs de Debug
Para obtener logs detallados:

```bash
# Configurar nivel de log
export LOG_LEVEL=DEBUG
python main.py
```

### Reporte de Problemas
Incluir en el reporte:
1. Logs relevantes (`logs/errors.log`)
2. Configuración (sin credenciales)
3. Pasos para reproducir el error
4. Versión del sistema operativo

## 🤝 Contribución

1. Fork del repositorio
2. Crear branch para feature (`git checkout -b feature/nueva-caracteristica`)
3. Commit cambios (`git commit -m 'Agregar nueva característica'`)
4. Push al branch (`git push origin feature/nueva-caracteristica`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

## 🙏 Reconocimientos

- OpenAI por la API de GPT
- Selenium para automatización web
- Loguru para logging elegante
- Instagrapi para Instagram API

---

**⭐ ¡Si este proyecto te fue útil, considera darle una estrella!**

**💬 ¿Preguntas? Abre un issue en GitHub**