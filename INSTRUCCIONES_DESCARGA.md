# 📥 INSTRUCCIONES DE DESCARGA - Agente de Marketing

## 🎯 ¿Qué has recibido?

Has recibido un **Agente de Marketing Automático** completo que:
- 🔍 Analiza competidores en Facebook e Instagram
- 🤖 Genera contenido con IA (OpenAI GPT)
- 📢 Publica automáticamente en tus redes sociales
- ⏰ Funciona 24/7 de forma automática

## 📦 Archivos Principales

1. **`agente_marketing_completo.json`** - Información completa del proyecto
2. **`proyecto_completo.json`** - Documentación técnica 
3. **Códigos fuente** - Todos los archivos Python están en el workspace

## 🚀 Instalación Rápida

### Paso 1: Descargar Python
```bash
# Necesitas Python 3.8+
python --version
```

### Paso 2: Instalar Dependencias
```bash
pip install -r requirements.txt
```

### Paso 3: Configuración Inicial
```bash
python main.py --setup
```

### Paso 4: Configurar Credenciales
Edita el archivo `.env` que se creó:
```env
# ⚠️ OBLIGATORIO - Sin esto no funciona
OPENAI_API_KEY=sk-tu-clave-de-openai-aqui

# 📘 OPCIONAL - Para publicar en Facebook
FACEBOOK_ACCESS_TOKEN=tu-token-facebook
FACEBOOK_PAGE_ID=tu-page-id

# 📷 OPCIONAL - Para publicar en Instagram  
INSTAGRAM_USERNAME=tu-usuario-instagram
INSTAGRAM_PASSWORD=tu-password-instagram
```

### Paso 5: Configurar Competidores
1. Abre `data/competidores.xlsx`
2. Agrega las URLs de Facebook e Instagram de tus competidores
3. Guarda el archivo

### Paso 6: ¡Ejecutar!
```bash
# Modo prueba (interactivo)
python main.py

# Modo automático (background)
python main.py --daemon
```

## 🔑 APIs Necesarias

### OpenAI API (OBLIGATORIO)
1. Ve a https://platform.openai.com/
2. Crea una cuenta
3. Genera una API key
4. Ponla en el archivo `.env`

### Facebook API (OPCIONAL)
1. Ve a https://developers.facebook.com/
2. Crea una app
3. Obtén tu access token y page ID
4. Ponlos en el archivo `.env`

### Instagram (OPCIONAL)
- Solo necesitas tu usuario y contraseña
- ⚠️ Desactiva 2FA temporalmente

## 📊 ¿Qué hace el agente?

### Cada 2 horas:
1. 🔍 **Analiza** las últimas 3 publicaciones de cada competidor
2. 📊 **Extrae** hashtags, temas exitosos, y patrones
3. 🧠 **Genera** contenido mejorado con IA
4. 💾 **Guarda** todo en una base de datos local

### Publicación automática:
- **Facebook**: 1 vez al día (09:00 por defecto)
- **Instagram**: 3 veces al día (09:00, 14:00, 19:00)

### Monitoreo 24/7:
- 📝 Logs detallados en `logs/`
- 📈 Métricas del sistema
- 🚨 Alertas automáticas si algo falla

## ⚡ Comandos Útiles

```bash
# Ver estado del agente
python main.py status

# Ejecutar solo scraping
python main.py scrape

# Generar contenido manualmente
python main.py generate

# Ejecutar pruebas
python main.py --test

# Ver ayuda completa
python main.py --help
```

## 🛠️ Solución de Problemas

### Error: "Chrome not found"
```bash
# Ubuntu/Debian
sudo apt install google-chrome-stable

# MacOS
brew install --cask google-chrome
```

### Error: "OpenAI API key invalid"
- Verifica que tu API key esté correcta
- Asegúrate de tener créditos en OpenAI

### Error: "Instagram login failed"
- Verifica usuario/contraseña
- Desactiva 2FA temporalmente
- Espera 10-15 minutos entre intentos

### Posts no se encuentran
- Verifica que las páginas sean públicas
- Revisa las URLs en el Excel

## 📞 Soporte

Si tienes problemas:
1. Revisa los logs en `logs/marketing_agent.log`
2. Ejecuta `python main.py --test` para diagnóstico
3. Verifica que todas las dependencias estén instaladas

## 🎉 ¡Listo para Usar!

Una vez configurado, el agente funcionará automáticamente:
- Analizará competidores cada 2 horas
- Generará contenido inteligente
- Publicará en horarios optimizados
- Te enviará reportes de actividad

**¡Disfruta de tu agente de marketing automático! 🚀**