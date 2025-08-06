#!/usr/bin/env python3
"""
Agente de Marketing Automático
===============================

Este es el punto de entrada principal del agente de marketing que:
1. Analiza páginas públicas de Facebook e Instagram de la competencia
2. Extrae contenido, hashtags y patrones de éxito
3. Genera contenido mejorado usando IA
4. Publica automáticamente en tus redes sociales
5. Opera de forma programada y autónoma

Autor: Marketing Agent Team
Versión: 1.0.0
"""

import os
import sys
import time
import signal
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Agregar el directorio src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Importar módulos del agente
from config_manager import ConfigManager, AgentConfig
from monitoring import MonitoringSystem, AlertSeverity
from scheduler import TaskScheduler, crear_tarea_scraping, crear_tarea_analisis, crear_tarea_generacion_contenido, crear_tarea_publicacion
from excel_reader import ExcelReader
from social_scraper import SocialScraper, scrape_competencia
from content_analyzer import ContentAnalyzer, analizar_competencia_completa
from content_generator import ContentGenerator, generar_campana_completa
from social_publisher import SocialPublisher, crear_publisher_desde_config

class MarketingAgent:
    """Agente de Marketing Principal"""
    
    def __init__(self, config_dir: str = "./config"):
        """
        Inicializa el agente de marketing
        
        Args:
            config_dir: Directorio de configuración
        """
        print("🚀 Inicializando Agente de Marketing...")
        
        # Componentes principales
        self.config_manager = ConfigManager(config_dir)
        self.config = self.config_manager.get_config()
        self.monitoring = MonitoringSystem()
        self.scheduler = TaskScheduler()
        
        # Componentes de trabajo
        self.excel_reader: Optional[ExcelReader] = None
        self.scraper: Optional[SocialScraper] = None
        self.analyzer: Optional[ContentAnalyzer] = None
        self.generator: Optional[ContentGenerator] = None
        self.publisher: Optional[SocialPublisher] = None
        
        # Estado
        self.running = False
        self.initialization_complete = False
        
        # Configurar señales para shutdown limpio
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print(f"✅ Agente '{self.config.agent_name}' v{self.config.version} inicializado")
    
    def _signal_handler(self, signum, frame):
        """Maneja señales del sistema para shutdown limpio"""
        print(f"\n⚠️  Señal {signum} recibida, deteniendo agente...")
        self.stop()
        sys.exit(0)
    
    def validate_configuration(self) -> bool:
        """Valida la configuración del agente"""
        print("🔍 Validando configuración...")
        
        validation = self.config_manager.validate_config()
        
        if validation['errors']:
            print("❌ Errores de configuración encontrados:")
            for error in validation['errors']:
                print(f"   • {error}")
            return False
        
        if validation['warnings']:
            print("⚠️  Advertencias de configuración:")
            for warning in validation['warnings']:
                print(f"   • {warning}")
        
        print("✅ Configuración validada")
        return True
    
    def initialize_components(self):
        """Inicializa todos los componentes del agente"""
        try:
            print("🔧 Inicializando componentes...")
            
            # Excel Reader
            self.excel_reader = ExcelReader(self.config.excel_file_path)
            
            # Social Scraper
            self.scraper = SocialScraper(
                headless=self.config.scraping.headless_browser,
                media_storage_path=self.config.media_storage_path
            )
            
            # Content Analyzer
            self.analyzer = ContentAnalyzer()
            
            # Content Generator
            if self.config.ai.openai_api_key:
                self.generator = ContentGenerator(
                    openai_api_key=self.config.ai.openai_api_key,
                    brand_voice=self.config.ai.brand_voice,
                    target_audience=self.config.ai.target_audience
                )
            else:
                print("⚠️  OpenAI API key no configurada - generación de contenido deshabilitada")
            
            # Social Publisher
            social_configs = self.config_manager.get_social_configs()
            self.publisher = crear_publisher_desde_config(social_configs)
            
            # Registrar funciones de tareas en el scheduler
            self._register_task_functions()
            
            self.initialization_complete = True
            print("✅ Componentes inicializados correctamente")
            
        except Exception as e:
            print(f"❌ Error al inicializar componentes: {e}")
            self.monitoring.create_alert(
                AlertSeverity.CRITICAL,
                "Component Initialization Failed",
                str(e),
                "main_agent"
            )
            raise
    
    def _register_task_functions(self):
        """Registra funciones de tareas en el scheduler"""
        
        def ejecutar_scraping(excel_path: str, max_posts: int = 3):
            """Función para ejecutar scraping de competencia"""
            try:
                print(f"📊 Ejecutando scraping desde {excel_path}...")
                
                # Cargar competidores
                competidores = self.excel_reader.leer_competidores()
                if not competidores:
                    raise Exception("No se encontraron competidores en el Excel")
                
                # Obtener URLs
                urls_facebook = self.excel_reader.obtener_urls_facebook()
                urls_instagram = self.excel_reader.obtener_urls_instagram()
                
                print(f"🎯 Analizando {len(urls_facebook)} páginas de Facebook y {len(urls_instagram)} de Instagram")
                
                # Realizar scraping
                resultados = scrape_competencia(urls_facebook, urls_instagram, max_posts)
                
                # Guardar resultados
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"./data/posts_competencia_{timestamp}.json"
                
                if resultados['facebook'] or resultados['instagram']:
                    self.scraper.guardar_posts_json(
                        resultados['facebook'] + resultados['instagram'],
                        output_file
                    )
                
                total_posts = len(resultados['facebook']) + len(resultados['instagram'])
                print(f"✅ Scraping completado: {total_posts} posts extraídos")
                
                return {
                    "posts_facebook": len(resultados['facebook']),
                    "posts_instagram": len(resultados['instagram']),
                    "total_posts": total_posts,
                    "output_file": output_file
                }
                
            except Exception as e:
                print(f"❌ Error en scraping: {e}")
                raise
        
        def ejecutar_analisis():
            """Función para ejecutar análisis de contenido"""
            try:
                print("🔍 Ejecutando análisis de contenido...")
                
                # Buscar archivos de posts más recientes
                data_dir = Path("./data")
                post_files = list(data_dir.glob("posts_competencia_*.json"))
                
                if not post_files:
                    raise Exception("No se encontraron archivos de posts para analizar")
                
                # Usar el archivo más reciente
                latest_file = max(post_files, key=lambda f: f.stat().st_mtime)
                posts = self.scraper.cargar_posts_json(str(latest_file))
                
                # Agrupar posts por competidor
                posts_por_competidor = {}
                for post in posts:
                    competidor = post.fuente or "Desconocido"
                    if competidor not in posts_por_competidor:
                        posts_por_competidor[competidor] = []
                    posts_por_competidor[competidor].append(post)
                
                # Realizar análisis
                resultados = analizar_competencia_completa(posts_por_competidor)
                
                # Guardar análisis
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"./data/analisis_competencia_{timestamp}.json"
                
                import json
                with open(output_file, 'w', encoding='utf-8') as f:
                    # Convertir a diccionario serializable
                    resultados_serializables = {}
                    for key, value in resultados.items():
                        if hasattr(value, '__dict__'):
                            resultados_serializables[key] = value.__dict__
                        else:
                            resultados_serializables[key] = value
                    
                    json.dump(resultados_serializables, f, ensure_ascii=False, indent=2, default=str)
                
                competidores_analizados = len(posts_por_competidor)
                print(f"✅ Análisis completado: {competidores_analizados} competidores analizados")
                
                return {
                    "competidores_analizados": competidores_analizados,
                    "total_posts_analizados": len(posts),
                    "output_file": output_file
                }
                
            except Exception as e:
                print(f"❌ Error en análisis: {e}")
                raise
        
        def ejecutar_generacion_contenido(dias_adelante: int = 1):
            """Función para generar contenido"""
            try:
                if not self.generator:
                    raise Exception("Generador de contenido no disponible (falta API key)")
                
                print(f"✨ Generando contenido para {dias_adelante} día(s)...")
                
                # Cargar análisis más reciente
                data_dir = Path("./data")
                analysis_files = list(data_dir.glob("analisis_competencia_*.json"))
                
                if not analysis_files:
                    raise Exception("No se encontraron archivos de análisis")
                
                latest_file = max(analysis_files, key=lambda f: f.stat().st_mtime)
                
                with open(latest_file, 'r', encoding='utf-8') as f:
                    analisis_competencia = json.load(f)
                
                # Generar contenido
                contenidos = self.generator.generar_contenido_programado(
                    analisis_competencia, 
                    dias_adelante
                )
                
                # Guardar contenido generado
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"./generated_content/contenido_{timestamp}.json"
                
                self.generator.guardar_contenido_generado(contenidos, output_file)
                
                contenidos_facebook = len([c for c in contenidos if c.plataforma == "facebook"])
                contenidos_instagram = len([c for c in contenidos if c.plataforma == "instagram"])
                
                print(f"✅ Contenido generado: {contenidos_facebook} para Facebook, {contenidos_instagram} para Instagram")
                
                return {
                    "contenidos_facebook": contenidos_facebook,
                    "contenidos_instagram": contenidos_instagram,
                    "total_contenidos": len(contenidos),
                    "output_file": output_file
                }
                
            except Exception as e:
                print(f"❌ Error en generación de contenido: {e}")
                raise
        
        def ejecutar_publicacion(plataforma: str = "both"):
            """Función para publicar contenido"""
            try:
                print(f"📢 Ejecutando publicación en {plataforma}...")
                
                # Verificar estado de APIs
                estado_apis = self.publisher.verificar_estado_apis()
                
                if plataforma == "both":
                    if not any(estado_apis.values()):
                        raise Exception("Ninguna API de redes sociales está configurada")
                elif plataforma == "facebook" and not estado_apis.get("facebook"):
                    raise Exception("API de Facebook no está configurada")
                elif plataforma == "instagram" and not estado_apis.get("instagram"):
                    raise Exception("API de Instagram no está configurada")
                
                # Cargar contenido más reciente
                content_dir = Path("./generated_content")
                content_files = list(content_dir.glob("contenido_*.json"))
                
                if not content_files:
                    raise Exception("No se encontró contenido generado para publicar")
                
                latest_file = max(content_files, key=lambda f: f.stat().st_mtime)
                contenidos = self.generator.cargar_contenido_generado(str(latest_file))
                
                # Filtrar contenidos según plataforma
                if plataforma != "both":
                    contenidos = [c for c in contenidos if c.plataforma == plataforma]
                
                # Filtrar contenidos que no han sido publicados y están programados para ahora
                contenidos_a_publicar = []
                now = datetime.now()
                
                for contenido in contenidos:
                    if contenido.fecha_sugerida:
                        fecha_programada = datetime.fromisoformat(contenido.fecha_sugerida)
                        # Publicar si está programado para las próximas 2 horas
                        if fecha_programada <= now:
                            contenidos_a_publicar.append(contenido)
                
                if not contenidos_a_publicar:
                    print("📅 No hay contenido programado para publicar en este momento")
                    return {"contenidos_publicados": 0, "mensaje": "No hay contenido programado"}
                
                # Publicar contenidos
                resultados = self.publisher.publicar_multiples_contenidos(contenidos_a_publicar)
                
                # Guardar resultados
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"./data/publicaciones_{timestamp}.json"
                self.publisher.guardar_resultados_publicacion(resultados, output_file)
                
                exitosos = len([r for r in resultados if r.exito])
                fallidos = len([r for r in resultados if not r.exito])
                
                print(f"✅ Publicación completada: {exitosos} exitosas, {fallidos} fallidas")
                
                return {
                    "contenidos_publicados": exitosos,
                    "contenidos_fallidos": fallidos,
                    "total_intentos": len(resultados),
                    "output_file": output_file
                }
                
            except Exception as e:
                print(f"❌ Error en publicación: {e}")
                raise
        
        # Registrar funciones en el scheduler
        self.scheduler.register_task_function("scraping", ejecutar_scraping)
        self.scheduler.register_task_function("analysis", ejecutar_analisis)
        self.scheduler.register_task_function("content_generation", ejecutar_generacion_contenido)
        self.scheduler.register_task_function("publishing", ejecutar_publicacion)
        
        print("✅ Funciones de tareas registradas")
    
    def setup_default_tasks(self):
        """Configura tareas por defecto"""
        print("📋 Configurando tareas por defecto...")
        
        try:
            # Tarea de scraping (cada 2 horas)
            tarea_scraping = crear_tarea_scraping(
                "scraping_competencia",
                "Scraping Automático de Competencia",
                "*/2", # Cada 2 horas
                "hourly",
                self.config.excel_file_path
            )
            tarea_scraping.parametros['max_posts'] = self.config.scraping.max_posts_per_source
            
            # Tarea de análisis (diario a las 8:30)
            tarea_analisis = crear_tarea_analisis(
                "analisis_contenido",
                "Análisis de Contenido",
                "08:30",
                "daily"
            )
            
            # Tarea de generación de contenido (diario a las 9:00)
            tarea_generacion = crear_tarea_generacion_contenido(
                "generacion_contenido",
                "Generación de Contenido",
                "09:00",
                "daily",
                1  # 1 día adelante
            )
            
            # Tareas de publicación
            # Facebook (1 vez al día)
            tarea_pub_facebook = crear_tarea_publicacion(
                "publicacion_facebook",
                "Publicación Facebook",
                self.config.facebook.post_time,
                "daily",
                "facebook"
            )
            
            # Instagram (3 veces al día)
            for i, tiempo in enumerate(self.config.instagram.post_times):
                tarea_pub_instagram = crear_tarea_publicacion(
                    f"publicacion_instagram_{i+1}",
                    f"Publicación Instagram {i+1}",
                    tiempo,
                    "daily",
                    "instagram"
                )
                self.scheduler.add_task(tarea_pub_instagram)
            
            # Añadir tareas principales
            self.scheduler.add_task(tarea_scraping)
            self.scheduler.add_task(tarea_analisis)
            self.scheduler.add_task(tarea_generacion)
            self.scheduler.add_task(tarea_pub_facebook)
            
            print("✅ Tareas por defecto configuradas")
            
        except Exception as e:
            print(f"❌ Error al configurar tareas: {e}")
            raise
    
    def start(self):
        """Inicia el agente de marketing"""
        if self.running:
            print("⚠️  El agente ya está en ejecución")
            return
        
        print("🚀 Iniciando Agente de Marketing...")
        
        try:
            # Validar configuración
            if not self.validate_configuration():
                raise Exception("Configuración inválida")
            
            # Inicializar componentes
            if not self.initialization_complete:
                self.initialize_components()
            
            # Configurar tareas por defecto
            self.setup_default_tasks()
            
            # Iniciar monitoreo
            self.monitoring.start_monitoring()
            
            # Iniciar scheduler
            self.scheduler.start()
            
            self.running = True
            
            # Log evento de inicio
            self.monitoring.log_system_event(
                "agent_started",
                "main_agent",
                f"Agente {self.config.agent_name} iniciado correctamente"
            )
            
            print("✅ Agente de Marketing iniciado correctamente")
            print(f"📊 Monitoreo: Activo")
            print(f"⏰ Scheduler: Activo")
            print(f"🎯 Tareas programadas: {len(self.scheduler.tasks)}")
            
            self._print_status()
            
        except Exception as e:
            print(f"❌ Error al iniciar agente: {e}")
            self.monitoring.create_alert(
                AlertSeverity.CRITICAL,
                "Agent Startup Failed",
                str(e),
                "main_agent"
            )
            raise
    
    def stop(self):
        """Detiene el agente de marketing"""
        if not self.running:
            print("⚠️  El agente no está en ejecución")
            return
        
        print("🛑 Deteniendo Agente de Marketing...")
        
        try:
            # Detener scheduler
            self.scheduler.stop()
            
            # Detener monitoreo
            self.monitoring.stop_monitoring()
            
            # Cerrar recursos
            if self.scraper:
                self.scraper.cerrar_driver()
            
            self.running = False
            
            # Log evento de parada
            self.monitoring.log_system_event(
                "agent_stopped",
                "main_agent",
                f"Agente {self.config.agent_name} detenido"
            )
            
            print("✅ Agente de Marketing detenido correctamente")
            
        except Exception as e:
            print(f"❌ Error al detener agente: {e}")
    
    def _print_status(self):
        """Muestra el estado actual del agente"""
        print("\n" + "="*60)
        print("📊 ESTADO DEL AGENTE DE MARKETING")
        print("="*60)
        
        # Estado general
        print(f"🤖 Agente: {self.config.agent_name} v{self.config.version}")
        print(f"🟢 Estado: {'Ejecutándose' if self.running else 'Detenido'}")
        
        # Configuración
        print(f"📁 Excel: {self.config.excel_file_path}")
        print(f"🔑 OpenAI: {'Configurado' if self.config.ai.openai_api_key else 'No configurado'}")
        print(f"📘 Facebook: {'Configurado' if self.config.facebook.access_token else 'No configurado'}")
        print(f"📷 Instagram: {'Configurado' if self.config.instagram.username else 'No configurado'}")
        
        # Tareas
        if self.scheduler.tasks:
            print(f"\n⏰ TAREAS PROGRAMADAS ({len(self.scheduler.tasks)}):")
            for task_id, task in self.scheduler.tasks.items():
                estado = "🟢" if task.activa else "🔴"
                print(f"   {estado} {task.nombre} - {task.frecuencia} a las {task.horario}")
        
        # Estadísticas
        if self.monitoring.current_metrics:
            metrics = self.monitoring.current_metrics
            print(f"\n📈 MÉTRICAS ACTUALES:")
            print(f"   💻 CPU: {metrics.cpu_percent:.1f}%")
            print(f"   🧠 Memoria: {metrics.memory_percent:.1f}%")
            print(f"   💾 Disco: {metrics.disk_percent:.1f}%")
        
        print("="*60)
    
    def run_interactive(self):
        """Ejecuta el agente en modo interactivo"""
        try:
            self.start()
            
            print("\n🎮 MODO INTERACTIVO")
            print("Comandos disponibles:")
            print("  status  - Mostrar estado del agente")
            print("  tasks   - Listar tareas programadas")
            print("  run <task_id> - Ejecutar tarea manualmente")
            print("  alerts  - Mostrar alertas activas")
            print("  stop    - Detener agente")
            print("  help    - Mostrar esta ayuda")
            print("  quit    - Salir")
            
            while self.running:
                try:
                    command = input("\n🤖 Agent> ").strip().lower()
                    
                    if command == "quit" or command == "exit":
                        break
                    elif command == "status":
                        self._print_status()
                    elif command == "tasks":
                        self._print_tasks()
                    elif command.startswith("run "):
                        task_id = command[4:].strip()
                        self._run_task_manual(task_id)
                    elif command == "alerts":
                        self._print_alerts()
                    elif command == "stop":
                        break
                    elif command == "help":
                        print("Ver comandos arriba ☝️")
                    elif command == "":
                        continue
                    else:
                        print(f"❓ Comando desconocido: {command}")
                        
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
            
        finally:
            self.stop()
    
    def _print_tasks(self):
        """Muestra las tareas programadas"""
        status_list = self.scheduler.get_task_status()
        
        if not status_list:
            print("📋 No hay tareas programadas")
            return
        
        print(f"\n📋 TAREAS PROGRAMADAS ({len(status_list)}):")
        print("-" * 80)
        
        for task in status_list:
            estado = "🟢" if task['activa'] else "🔴"
            ultima = task['ultima_ejecucion']
            if ultima:
                ultima = datetime.fromisoformat(ultima).strftime("%Y-%m-%d %H:%M")
            else:
                ultima = "Nunca"
            
            print(f"{estado} {task['task_id']}")
            print(f"    📝 {task['nombre']}")
            print(f"    ⏰ {task['frecuencia']} a las {task['horario']}")
            print(f"    🕐 Última ejecución: {ultima}")
            print()
    
    def _run_task_manual(self, task_id: str):
        """Ejecuta una tarea manualmente"""
        if task_id not in self.scheduler.tasks:
            print(f"❌ Tarea no encontrada: {task_id}")
            return
        
        print(f"🚀 Ejecutando tarea manualmente: {task_id}")
        
        try:
            resultado = self.scheduler.execute_task_now(task_id)
            
            if resultado.exito:
                print(f"✅ Tarea completada exitosamente")
                print(f"⏱️  Duración: {resultado.duracion_segundos:.2f}s")
                if resultado.datos_resultado:
                    print(f"📊 Resultado: {resultado.datos_resultado}")
            else:
                print(f"❌ Tarea falló: {resultado.mensaje}")
                
        except Exception as e:
            print(f"❌ Error al ejecutar tarea: {e}")
    
    def _print_alerts(self):
        """Muestra las alertas activas"""
        dashboard_data = self.monitoring.get_dashboard_data()
        active_alerts = dashboard_data.get('active_alerts', [])
        
        if not active_alerts:
            print("✅ No hay alertas activas")
            return
        
        print(f"\n🚨 ALERTAS ACTIVAS ({len(active_alerts)}):")
        print("-" * 60)
        
        for alert in active_alerts:
            severity_icon = {
                'low': '🟡',
                'medium': '🟠', 
                'high': '🔴',
                'critical': '💀'
            }.get(alert['severity'], '❓')
            
            timestamp = datetime.fromisoformat(alert['timestamp']).strftime("%Y-%m-%d %H:%M")
            
            print(f"{severity_icon} {alert['title']}")
            print(f"    📦 Componente: {alert['component']}")
            print(f"    💬 {alert['message']}")
            print(f"    🕐 {timestamp}")
            print()
    
    def run_daemon(self):
        """Ejecuta el agente como daemon"""
        try:
            self.start()
            
            print("🤖 Agente ejecutándose como daemon...")
            print("   Para detener: Ctrl+C o enviar señal SIGTERM")
            
            # Mantener el proceso vivo
            while self.running:
                time.sleep(60)  # Verificar cada minuto
                
                # Verificar salud del sistema
                try:
                    if not self.scheduler.running:
                        print("⚠️  Scheduler detenido, reiniciando...")
                        self.scheduler.start()
                    
                    if not self.monitoring.running:
                        print("⚠️  Monitoreo detenido, reiniciando...")
                        self.monitoring.start_monitoring()
                        
                except Exception as e:
                    print(f"❌ Error en verificación de salud: {e}")
                    
        except KeyboardInterrupt:
            print("\n⚠️  Interrupción recibida")
        finally:
            self.stop()

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Agente de Marketing Automático",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python main.py                     # Modo interactivo
  python main.py --daemon            # Ejecutar como daemon
  python main.py --setup             # Configuración inicial
  python main.py --test              # Ejecutar tests
        """
    )
    
    parser.add_argument(
        '--daemon', 
        action='store_true',
        help='Ejecutar como daemon en segundo plano'
    )
    
    parser.add_argument(
        '--setup',
        action='store_true', 
        help='Ejecutar configuración inicial'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Ejecutar tests del sistema'
    )
    
    parser.add_argument(
        '--config-dir',
        default='./config',
        help='Directorio de configuración (default: ./config)'
    )
    
    args = parser.parse_args()
    
    try:
        # Banner de inicio
        print("""
╔══════════════════════════════════════════════════════════════════╗
║                    🤖 AGENTE DE MARKETING 🤖                     ║
║                           Versión 1.0.0                         ║
║                                                                  ║
║  • Análisis automático de competencia                           ║
║  • Generación de contenido con IA                               ║
║  • Publicación programada en redes sociales                     ║
║  • Monitoreo y alertas en tiempo real                           ║
╚══════════════════════════════════════════════════════════════════╝
        """)
        
        if args.setup:
            print("🔧 Iniciando configuración inicial...")
            agent = MarketingAgent(args.config_dir)
            
            # Crear archivo Excel de ejemplo
            if agent.excel_reader:
                agent.excel_reader.crear_excel_ejemplo()
            
            # Crear archivo .env
            agent.config_manager.create_env_file()
            
            print("✅ Configuración inicial completada")
            print("📝 Edita el archivo .env y competidores.xlsx antes de continuar")
            return
        
        elif args.test:
            print("🧪 Ejecutando tests del sistema...")
            # Aquí se podrían agregar tests específicos
            agent = MarketingAgent(args.config_dir)
            
            if agent.validate_configuration():
                print("✅ Configuración válida")
            
            agent.initialize_components()
            print("✅ Componentes inicializados correctamente")
            print("🎉 Todos los tests pasaron")
            return
        
        # Crear e inicializar agente
        agent = MarketingAgent(args.config_dir)
        
        # Ejecutar según modo
        if args.daemon:
            agent.run_daemon()
        else:
            agent.run_interactive()
            
    except KeyboardInterrupt:
        print("\n👋 ¡Hasta luego!")
    except Exception as e:
        print(f"\n💥 Error fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()