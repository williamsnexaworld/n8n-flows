"""
Sistema de logging y monitoreo para el agente de marketing
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3
from contextlib import contextmanager
import psutil
import sys
from loguru import logger
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import requests
from enum import Enum

class LogLevel(Enum):
    """Niveles de log"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class AlertSeverity(Enum):
    """Severidad de alertas"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SystemMetrics:
    """Métricas del sistema"""
    timestamp: str
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    active_tasks: int
    successful_tasks_24h: int
    failed_tasks_24h: int
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

@dataclass
class Alert:
    """Alerta del sistema"""
    alert_id: str
    severity: AlertSeverity
    title: str
    message: str
    component: str
    timestamp: str = ""
    resolved: bool = False
    resolved_at: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}

@dataclass
class HealthCheck:
    """Estado de salud de un componente"""
    component: str
    status: str  # 'healthy', 'warning', 'error'
    message: str
    last_check: str
    response_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if not self.last_check:
            self.last_check = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}

class MonitoringSystem:
    """Sistema de monitoreo y logging"""
    
    def __init__(self, db_path: str = "./data/monitoring.db", log_dir: str = "./logs"):
        """
        Inicializa el sistema de monitoreo
        
        Args:
            db_path: Ruta de la base de datos de monitoreo
            log_dir: Directorio de logs
        """
        self.db_path = db_path
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuración
        self.monitoring_enabled = True
        self.metrics_interval = 60  # segundos
        self.health_check_interval = 300  # 5 minutos
        self.retention_days = 30
        
        # Estados
        self.running = False
        self.monitoring_thread = None
        self.health_check_thread = None
        
        # Callbacks y hooks
        self.alert_callbacks: List[Callable] = []
        self.health_check_functions: Dict[str, Callable] = {}
        
        # Métricas en memoria
        self.current_metrics: Optional[SystemMetrics] = None
        self.alerts_cache: List[Alert] = []
        self.health_status: Dict[str, HealthCheck] = {}
        
        # Configurar logging
        self._setup_logging()
        
        # Inicializar base de datos
        self._init_database()
        
        # Registrar health checks básicos
        self._register_default_health_checks()
        
        logger.info("Sistema de monitoreo inicializado")
    
    def _setup_logging(self):
        """Configura el sistema de logging"""
        try:
            # Remover handlers existentes
            logger.remove()
            
            # Configurar formato
            log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
            
            # Handler para consola
            logger.add(
                sys.stdout,
                format=log_format,
                level="INFO",
                colorize=True
            )
            
            # Handler para archivo principal
            main_log_file = self.log_dir / "marketing_agent.log"
            logger.add(
                main_log_file,
                format=log_format,
                level="DEBUG",
                rotation="10 MB",
                retention="30 days",
                compression="zip",
                encoding="utf-8"
            )
            
            # Handler para errores
            error_log_file = self.log_dir / "errors.log"
            logger.add(
                error_log_file,
                format=log_format,
                level="ERROR",
                rotation="5 MB",
                retention="60 days",
                compression="zip",
                encoding="utf-8"
            )
            
            # Handler para métricas
            metrics_log_file = self.log_dir / "metrics.log"
            logger.add(
                metrics_log_file,
                format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
                level="INFO",
                filter=lambda record: record["extra"].get("type") == "metrics",
                rotation="1 day",
                retention="30 days",
                encoding="utf-8"
            )
            
            logger.info("Sistema de logging configurado")
            
        except Exception as e:
            print(f"Error al configurar logging: {e}")
    
    def _init_database(self):
        """Inicializa la base de datos de monitoreo"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Tabla de métricas
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP NOT NULL,
                        cpu_percent REAL,
                        memory_percent REAL,
                        disk_percent REAL,
                        network_bytes_sent INTEGER,
                        network_bytes_recv INTEGER,
                        active_tasks INTEGER,
                        successful_tasks_24h INTEGER,
                        failed_tasks_24h INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Tabla de alertas
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS alerts (
                        alert_id TEXT PRIMARY KEY,
                        severity TEXT NOT NULL,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        component TEXT NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        resolved BOOLEAN DEFAULT FALSE,
                        resolved_at TIMESTAMP,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Tabla de health checks
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS health_checks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        component TEXT NOT NULL,
                        status TEXT NOT NULL,
                        message TEXT NOT NULL,
                        response_time_ms REAL,
                        timestamp TIMESTAMP NOT NULL,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Tabla de eventos del sistema
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS system_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        component TEXT NOT NULL,
                        message TEXT NOT NULL,
                        level TEXT NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Índices
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics (timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts (timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts (resolved)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_health_checks_component ON health_checks (component)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_system_events_timestamp ON system_events (timestamp)')
                
                conn.commit()
                logger.info("Base de datos de monitoreo inicializada")
                
        except Exception as e:
            logger.error(f"Error al inicializar base de datos de monitoreo: {e}")
            raise
    
    @contextmanager
    def _get_db_connection(self):
        """Context manager para conexiones a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()
    
    def _register_default_health_checks(self):
        """Registra health checks por defecto"""
        self.register_health_check("system_resources", self._check_system_resources)
        self.register_health_check("disk_space", self._check_disk_space)
        self.register_health_check("database", self._check_database)
        self.register_health_check("log_files", self._check_log_files)
    
    def _check_system_resources(self) -> HealthCheck:
        """Verifica recursos del sistema"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            
            status = "healthy"
            message = f"CPU: {cpu_percent:.1f}%, Memory: {memory_percent:.1f}%"
            
            if cpu_percent > 80 or memory_percent > 80:
                status = "warning"
                message += " - Alto uso de recursos"
            
            if cpu_percent > 95 or memory_percent > 95:
                status = "error"
                message += " - Recursos críticos"
            
            return HealthCheck(
                component="system_resources",
                status=status,
                message=message,
                last_check=datetime.now().isoformat(),
                metadata={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent
                }
            )
            
        except Exception as e:
            return HealthCheck(
                component="system_resources",
                status="error",
                message=f"Error al verificar recursos: {e}",
                last_check=datetime.now().isoformat()
            )
    
    def _check_disk_space(self) -> HealthCheck:
        """Verifica espacio en disco"""
        try:
            disk_usage = psutil.disk_usage('/')
            disk_percent = disk_usage.percent
            
            status = "healthy"
            message = f"Uso de disco: {disk_percent:.1f}%"
            
            if disk_percent > 80:
                status = "warning"
                message += " - Poco espacio disponible"
            
            if disk_percent > 95:
                status = "error"
                message += " - Espacio crítico"
            
            return HealthCheck(
                component="disk_space",
                status=status,
                message=message,
                last_check=datetime.now().isoformat(),
                metadata={
                    "disk_percent": disk_percent,
                    "free_gb": disk_usage.free / (1024**3)
                }
            )
            
        except Exception as e:
            return HealthCheck(
                component="disk_space",
                status="error",
                message=f"Error al verificar disco: {e}",
                last_check=datetime.now().isoformat()
            )
    
    def _check_database(self) -> HealthCheck:
        """Verifica estado de la base de datos"""
        try:
            start_time = time.time()
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            response_time = (time.time() - start_time) * 1000
            
            status = "healthy"
            message = f"Base de datos accesible (respuesta: {response_time:.2f}ms)"
            
            if response_time > 1000:
                status = "warning"
                message += " - Respuesta lenta"
            
            return HealthCheck(
                component="database",
                status=status,
                message=message,
                last_check=datetime.now().isoformat(),
                response_time_ms=response_time
            )
            
        except Exception as e:
            return HealthCheck(
                component="database",
                status="error",
                message=f"Error de base de datos: {e}",
                last_check=datetime.now().isoformat()
            )
    
    def _check_log_files(self) -> HealthCheck:
        """Verifica estado de archivos de log"""
        try:
            log_files = list(self.log_dir.glob("*.log"))
            total_size = sum(f.stat().st_size for f in log_files) / (1024**2)  # MB
            
            status = "healthy"
            message = f"{len(log_files)} archivos de log ({total_size:.1f} MB)"
            
            if total_size > 100:
                status = "warning"
                message += " - Tamaño grande de logs"
            
            if total_size > 500:
                status = "error"
                message += " - Logs ocupan mucho espacio"
            
            return HealthCheck(
                component="log_files",
                status=status,
                message=message,
                last_check=datetime.now().isoformat(),
                metadata={
                    "file_count": len(log_files),
                    "total_size_mb": total_size
                }
            )
            
        except Exception as e:
            return HealthCheck(
                component="log_files",
                status="error",
                message=f"Error al verificar logs: {e}",
                last_check=datetime.now().isoformat()
            )
    
    def collect_system_metrics(self) -> SystemMetrics:
        """Recolecta métricas del sistema"""
        try:
            # Métricas básicas del sistema
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()
            
            # Métricas de tareas (placeholder - se conectaría con el scheduler)
            active_tasks = 0
            successful_tasks_24h = 0
            failed_tasks_24h = 0
            
            # Intentar obtener métricas de tareas si el scheduler está disponible
            try:
                # Esto se conectaría con el TaskScheduler real
                pass
            except:
                pass
            
            metrics = SystemMetrics(
                timestamp=datetime.now().isoformat(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_percent=disk.percent,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                active_tasks=active_tasks,
                successful_tasks_24h=successful_tasks_24h,
                failed_tasks_24h=failed_tasks_24h
            )
            
            self.current_metrics = metrics
            
            # Guardar en base de datos
            self._save_metrics(metrics)
            
            # Log de métricas
            logger.bind(type="metrics").info(
                f"CPU:{cpu_percent:.1f}% MEM:{memory.percent:.1f}% DISK:{disk.percent:.1f}% "
                f"NET_SENT:{network.bytes_sent} NET_RECV:{network.bytes_recv}"
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error al recolectar métricas: {e}")
            raise
    
    def _save_metrics(self, metrics: SystemMetrics):
        """Guarda métricas en la base de datos"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO metrics (
                        timestamp, cpu_percent, memory_percent, disk_percent,
                        network_bytes_sent, network_bytes_recv, active_tasks,
                        successful_tasks_24h, failed_tasks_24h
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metrics.timestamp, metrics.cpu_percent, metrics.memory_percent,
                    metrics.disk_percent, metrics.network_bytes_sent, metrics.network_bytes_recv,
                    metrics.active_tasks, metrics.successful_tasks_24h, metrics.failed_tasks_24h
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error al guardar métricas: {e}")
    
    def create_alert(self, severity: AlertSeverity, title: str, message: str, 
                    component: str, metadata: Dict[str, Any] = None) -> Alert:
        """Crea una nueva alerta"""
        try:
            alert_id = f"{component}_{int(time.time())}"
            
            alert = Alert(
                alert_id=alert_id,
                severity=severity,
                title=title,
                message=message,
                component=component,
                metadata=metadata or {}
            )
            
            # Guardar en base de datos
            self._save_alert(alert)
            
            # Agregar a cache
            self.alerts_cache.append(alert)
            
            # Mantener solo las últimas 100 alertas en cache
            if len(self.alerts_cache) > 100:
                self.alerts_cache = self.alerts_cache[-100:]
            
            # Ejecutar callbacks
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Error en callback de alerta: {e}")
            
            # Log de alerta
            log_level = "warning" if severity in [AlertSeverity.LOW, AlertSeverity.MEDIUM] else "error"
            getattr(logger, log_level)(f"ALERT [{severity.value.upper()}] {component}: {title} - {message}")
            
            return alert
            
        except Exception as e:
            logger.error(f"Error al crear alerta: {e}")
            raise
    
    def _save_alert(self, alert: Alert):
        """Guarda alerta en la base de datos"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO alerts (
                        alert_id, severity, title, message, component,
                        timestamp, resolved, resolved_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert.alert_id, alert.severity.value, alert.title, alert.message,
                    alert.component, alert.timestamp, alert.resolved, alert.resolved_at,
                    json.dumps(alert.metadata) if alert.metadata else None
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error al guardar alerta: {e}")
    
    def resolve_alert(self, alert_id: str):
        """Resuelve una alerta"""
        try:
            resolved_at = datetime.now().isoformat()
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE alerts 
                    SET resolved = TRUE, resolved_at = ? 
                    WHERE alert_id = ?
                ''', (resolved_at, alert_id))
                conn.commit()
            
            # Actualizar cache
            for alert in self.alerts_cache:
                if alert.alert_id == alert_id:
                    alert.resolved = True
                    alert.resolved_at = resolved_at
                    break
            
            logger.info(f"Alerta resuelta: {alert_id}")
            
        except Exception as e:
            logger.error(f"Error al resolver alerta: {e}")
    
    def register_health_check(self, component: str, check_function: Callable):
        """Registra una función de health check"""
        self.health_check_functions[component] = check_function
        logger.info(f"Health check registrado para: {component}")
    
    def register_alert_callback(self, callback: Callable):
        """Registra un callback para alertas"""
        self.alert_callbacks.append(callback)
        logger.info("Callback de alerta registrado")
    
    def run_health_checks(self):
        """Ejecuta todos los health checks"""
        try:
            for component, check_function in self.health_check_functions.items():
                try:
                    health_check = check_function()
                    self.health_status[component] = health_check
                    
                    # Guardar en base de datos
                    self._save_health_check(health_check)
                    
                    # Crear alerta si hay problema
                    if health_check.status == "error":
                        self.create_alert(
                            AlertSeverity.HIGH,
                            f"Health Check Failed: {component}",
                            health_check.message,
                            component
                        )
                    elif health_check.status == "warning":
                        self.create_alert(
                            AlertSeverity.MEDIUM,
                            f"Health Check Warning: {component}",
                            health_check.message,
                            component
                        )
                    
                except Exception as e:
                    logger.error(f"Error en health check de {component}: {e}")
                    error_check = HealthCheck(
                        component=component,
                        status="error",
                        message=f"Health check failed: {e}",
                        last_check=datetime.now().isoformat()
                    )
                    self.health_status[component] = error_check
                    self._save_health_check(error_check)
            
        except Exception as e:
            logger.error(f"Error al ejecutar health checks: {e}")
    
    def _save_health_check(self, health_check: HealthCheck):
        """Guarda health check en la base de datos"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO health_checks (
                        component, status, message, response_time_ms, timestamp, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    health_check.component, health_check.status, health_check.message,
                    health_check.response_time_ms, health_check.last_check,
                    json.dumps(health_check.metadata) if health_check.metadata else None
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error al guardar health check: {e}")
    
    def log_system_event(self, event_type: str, component: str, message: str, 
                        level: LogLevel = LogLevel.INFO, metadata: Dict[str, Any] = None):
        """Registra un evento del sistema"""
        try:
            timestamp = datetime.now().isoformat()
            
            # Guardar en base de datos
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO system_events (
                        event_type, component, message, level, timestamp, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    event_type, component, message, level.value, timestamp,
                    json.dumps(metadata) if metadata else None
                ))
                conn.commit()
            
            # Log regular
            getattr(logger, level.value.lower())(f"[{component}] {event_type}: {message}")
            
        except Exception as e:
            logger.error(f"Error al registrar evento del sistema: {e}")
    
    def start_monitoring(self):
        """Inicia el monitoreo automático"""
        if self.running:
            logger.warning("El monitoreo ya está en ejecución")
            return
        
        logger.info("Iniciando sistema de monitoreo...")
        self.running = True
        
        # Thread para métricas
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        # Thread para health checks
        self.health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.health_check_thread.start()
        
        logger.info("Sistema de monitoreo iniciado")
    
    def stop_monitoring(self):
        """Detiene el monitoreo"""
        if not self.running:
            logger.warning("El monitoreo no está en ejecución")
            return
        
        logger.info("Deteniendo sistema de monitoreo...")
        self.running = False
        
        # Esperar que terminen los threads
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        
        if self.health_check_thread and self.health_check_thread.is_alive():
            self.health_check_thread.join(timeout=5)
        
        logger.info("Sistema de monitoreo detenido")
    
    def _monitoring_loop(self):
        """Loop principal de monitoreo de métricas"""
        while self.running:
            try:
                self.collect_system_metrics()
                time.sleep(self.metrics_interval)
            except Exception as e:
                logger.error(f"Error en loop de monitoreo: {e}")
                time.sleep(10)
    
    def _health_check_loop(self):
        """Loop de health checks"""
        while self.running:
            try:
                self.run_health_checks()
                time.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Error en loop de health checks: {e}")
                time.sleep(30)
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Obtiene datos para dashboard"""
        try:
            # Métricas actuales
            current_metrics = self.current_metrics
            
            # Alertas activas
            active_alerts = [alert for alert in self.alerts_cache if not alert.resolved]
            
            # Estado de salud
            health_summary = {
                "healthy": len([h for h in self.health_status.values() if h.status == "healthy"]),
                "warning": len([h for h in self.health_status.values() if h.status == "warning"]),
                "error": len([h for h in self.health_status.values() if h.status == "error"])
            }
            
            # Estadísticas de las últimas 24 horas
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Alertas de las últimas 24 horas
                cursor.execute('''
                    SELECT severity, COUNT(*) 
                    FROM alerts 
                    WHERE timestamp > datetime('now', '-24 hours')
                    GROUP BY severity
                ''')
                alerts_24h = dict(cursor.fetchall())
                
                # Métricas promedio de la última hora
                cursor.execute('''
                    SELECT AVG(cpu_percent), AVG(memory_percent), AVG(disk_percent)
                    FROM metrics 
                    WHERE timestamp > datetime('now', '-1 hour')
                ''')
                avg_metrics = cursor.fetchone()
            
            return {
                "current_metrics": asdict(current_metrics) if current_metrics else None,
                "active_alerts": [asdict(alert) for alert in active_alerts],
                "health_summary": health_summary,
                "health_status": {k: asdict(v) for k, v in self.health_status.items()},
                "alerts_24h": alerts_24h,
                "avg_metrics_1h": {
                    "cpu_percent": avg_metrics[0] if avg_metrics[0] else 0,
                    "memory_percent": avg_metrics[1] if avg_metrics[1] else 0,
                    "disk_percent": avg_metrics[2] if avg_metrics[2] else 0
                } if avg_metrics else None,
                "monitoring_status": "running" if self.running else "stopped"
            }
            
        except Exception as e:
            logger.error(f"Error al obtener datos de dashboard: {e}")
            return {}
    
    def cleanup_old_data(self):
        """Limpia datos antiguos según política de retención"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=self.retention_days)).isoformat()
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Limpiar métricas antiguas
                cursor.execute('DELETE FROM metrics WHERE timestamp < ?', (cutoff_date,))
                metrics_deleted = cursor.rowcount
                
                # Limpiar health checks antiguos
                cursor.execute('DELETE FROM health_checks WHERE timestamp < ?', (cutoff_date,))
                health_deleted = cursor.rowcount
                
                # Limpiar eventos antiguos
                cursor.execute('DELETE FROM system_events WHERE timestamp < ?', (cutoff_date,))
                events_deleted = cursor.rowcount
                
                conn.commit()
            
            logger.info(f"Datos antiguos limpiados: {metrics_deleted} métricas, {health_deleted} health checks, {events_deleted} eventos")
            
        except Exception as e:
            logger.error(f"Error al limpiar datos antiguos: {e}")

# Funciones de utilidad para alertas
def create_email_alert_callback(smtp_server: str, smtp_port: int, username: str, 
                               password: str, recipients: List[str]) -> Callable:
    """Crea un callback para enviar alertas por email"""
    def email_callback(alert: Alert):
        try:
            if alert.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
                msg = MimeMultipart()
                msg['From'] = username
                msg['To'] = ', '.join(recipients)
                msg['Subject'] = f"[ALERT] {alert.title}"
                
                body = f"""
                Severidad: {alert.severity.value.upper()}
                Componente: {alert.component}
                Mensaje: {alert.message}
                Timestamp: {alert.timestamp}
                """
                
                msg.attach(MimeText(body, 'plain'))
                
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(username, password)
                text = msg.as_string()
                server.sendmail(username, recipients, text)
                server.quit()
                
                logger.info(f"Alerta enviada por email: {alert.alert_id}")
                
        except Exception as e:
            logger.error(f"Error al enviar alerta por email: {e}")
    
    return email_callback

def create_webhook_alert_callback(webhook_url: str) -> Callable:
    """Crea un callback para enviar alertas por webhook"""
    def webhook_callback(alert: Alert):
        try:
            if alert.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
                payload = {
                    "alert_id": alert.alert_id,
                    "severity": alert.severity.value,
                    "title": alert.title,
                    "message": alert.message,
                    "component": alert.component,
                    "timestamp": alert.timestamp
                }
                
                response = requests.post(webhook_url, json=payload, timeout=10)
                response.raise_for_status()
                
                logger.info(f"Alerta enviada por webhook: {alert.alert_id}")
                
        except Exception as e:
            logger.error(f"Error al enviar alerta por webhook: {e}")
    
    return webhook_callback

if __name__ == "__main__":
    # Ejemplo de uso
    monitoring = MonitoringSystem()
    
    # Registrar callback de ejemplo
    def log_alert(alert: Alert):
        print(f"Nueva alerta: {alert.title} - {alert.message}")
    
    monitoring.register_alert_callback(log_alert)
    
    # Iniciar monitoreo
    monitoring.start_monitoring()
    
    # Crear una alerta de prueba
    monitoring.create_alert(
        AlertSeverity.MEDIUM,
        "Test Alert",
        "Esta es una alerta de prueba",
        "test_component"
    )
    
    # Obtener datos de dashboard
    dashboard_data = monitoring.get_dashboard_data()
    print("Datos de dashboard:")
    print(f"  Alertas activas: {len(dashboard_data.get('active_alerts', []))}")
    print(f"  Estado de monitoreo: {dashboard_data.get('monitoring_status')}")
    
    print("Sistema de monitoreo funcionando correctamente")
    
    # En un entorno real, el programa seguiría corriendo
    # monitoring.stop_monitoring()