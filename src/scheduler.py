"""
Módulo para programar y ejecutar tareas automáticamente del agente de marketing
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, asdict
from loguru import logger
import schedule
from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3
from contextlib import contextmanager
import signal
import sys

@dataclass
class TaskConfig:
    """Configuración de una tarea programada"""
    task_id: str
    nombre: str
    tipo: str  # 'scraping', 'analysis', 'content_generation', 'publishing'
    frecuencia: str  # 'daily', 'hourly', 'weekly', 'custom'
    horario: str  # "HH:MM" o cron-like expression
    parametros: Dict[str, Any]
    activa: bool = True
    ultima_ejecucion: Optional[str] = None
    proxima_ejecucion: Optional[str] = None
    reintentos_maximos: int = 3
    reintento_actual: int = 0
    descripcion: str = ""
    dependencias: List[str] = None  # IDs de tareas que deben ejecutarse antes
    
    def __post_init__(self):
        if self.dependencias is None:
            self.dependencias = []

@dataclass
class TaskResult:
    """Resultado de la ejecución de una tarea"""
    task_id: str
    exito: bool
    timestamp: str
    duracion_segundos: float
    mensaje: str = ""
    datos_resultado: Dict[str, Any] = None
    error_details: Optional[str] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.datos_resultado is None:
            self.datos_resultado = {}

class TaskScheduler:
    """Programador de tareas automático"""
    
    def __init__(self, db_path: str = "./data/scheduler.db"):
        """
        Inicializa el programador de tareas
        
        Args:
            db_path: Ruta de la base de datos SQLite
        """
        self.db_path = db_path
        self.tasks: Dict[str, TaskConfig] = {}
        self.task_functions: Dict[str, Callable] = {}
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.scheduler_thread = None
        
        # Configurar base de datos
        self._init_database()
        
        # Cargar tareas desde DB
        self._load_tasks_from_db()
        
        # Registrar señales para shutdown limpio
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("TaskScheduler inicializado")
    
    def _init_database(self):
        """Inicializa la base de datos SQLite"""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Tabla de tareas
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        config TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Tabla de resultados de ejecución
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS task_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        result TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (task_id) REFERENCES tasks (task_id)
                    )
                ''')
                
                # Índices para mejor performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_results_task_id ON task_results (task_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_results_created_at ON task_results (created_at)')
                
                conn.commit()
                logger.info("Base de datos inicializada correctamente")
                
        except Exception as e:
            logger.error(f"Error al inicializar base de datos: {e}")
            raise
    
    @contextmanager
    def _get_db_connection(self):
        """Context manager para conexiones a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()
    
    def _load_tasks_from_db(self):
        """Carga tareas desde la base de datos"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT task_id, config FROM tasks')
                
                for task_id, config_json in cursor.fetchall():
                    try:
                        config_dict = json.loads(config_json)
                        task_config = TaskConfig(**config_dict)
                        self.tasks[task_id] = task_config
                        logger.debug(f"Tarea cargada: {task_id}")
                    except Exception as e:
                        logger.error(f"Error al cargar tarea {task_id}: {e}")
                
                logger.info(f"Cargadas {len(self.tasks)} tareas desde la base de datos")
                
        except Exception as e:
            logger.error(f"Error al cargar tareas desde DB: {e}")
    
    def _save_task_to_db(self, task_config: TaskConfig):
        """Guarda una tarea en la base de datos"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                config_json = json.dumps(asdict(task_config), ensure_ascii=False)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO tasks (task_id, config, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (task_config.task_id, config_json))
                
                conn.commit()
                logger.debug(f"Tarea guardada en DB: {task_config.task_id}")
                
        except Exception as e:
            logger.error(f"Error al guardar tarea en DB: {e}")
    
    def _save_result_to_db(self, result: TaskResult):
        """Guarda resultado de ejecución en la base de datos"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                result_json = json.dumps(asdict(result), ensure_ascii=False)
                
                cursor.execute('''
                    INSERT INTO task_results (task_id, result)
                    VALUES (?, ?)
                ''', (result.task_id, result_json))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error al guardar resultado en DB: {e}")
    
    def register_task_function(self, task_type: str, function: Callable):
        """Registra una función para ejecutar un tipo de tarea específico"""
        self.task_functions[task_type] = function
        logger.info(f"Función registrada para tipo de tarea: {task_type}")
    
    def add_task(self, task_config: TaskConfig) -> bool:
        """Añade una nueva tarea programada"""
        try:
            # Validar configuración
            if not self._validate_task_config(task_config):
                return False
            
            # Calcular próxima ejecución
            task_config.proxima_ejecucion = self._calculate_next_execution(task_config)
            
            # Guardar en memoria y DB
            self.tasks[task_config.task_id] = task_config
            self._save_task_to_db(task_config)
            
            # Registrar en schedule si está corriendo
            if self.running:
                self._schedule_task(task_config)
            
            logger.info(f"Tarea añadida: {task_config.task_id} - {task_config.nombre}")
            return True
            
        except Exception as e:
            logger.error(f"Error al añadir tarea: {e}")
            return False
    
    def remove_task(self, task_id: str) -> bool:
        """Elimina una tarea programada"""
        try:
            if task_id in self.tasks:
                del self.tasks[task_id]
                
                # Eliminar de la base de datos
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
                    conn.commit()
                
                # Limpiar schedule
                schedule.clear(task_id)
                
                logger.info(f"Tarea eliminada: {task_id}")
                return True
            else:
                logger.warning(f"Tarea no encontrada: {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error al eliminar tarea: {e}")
            return False
    
    def update_task(self, task_config: TaskConfig) -> bool:
        """Actualiza una tarea existente"""
        try:
            if task_config.task_id not in self.tasks:
                logger.warning(f"Tarea no encontrada para actualizar: {task_config.task_id}")
                return False
            
            # Validar configuración
            if not self._validate_task_config(task_config):
                return False
            
            # Limpiar schedule anterior
            schedule.clear(task_config.task_id)
            
            # Actualizar configuración
            task_config.proxima_ejecucion = self._calculate_next_execution(task_config)
            self.tasks[task_config.task_id] = task_config
            self._save_task_to_db(task_config)
            
            # Re-programar si está corriendo
            if self.running:
                self._schedule_task(task_config)
            
            logger.info(f"Tarea actualizada: {task_config.task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error al actualizar tarea: {e}")
            return False
    
    def _validate_task_config(self, task_config: TaskConfig) -> bool:
        """Valida la configuración de una tarea"""
        if not task_config.task_id:
            logger.error("task_id es requerido")
            return False
        
        if not task_config.tipo:
            logger.error("tipo de tarea es requerido")
            return False
        
        if task_config.tipo not in self.task_functions:
            logger.error(f"No hay función registrada para el tipo: {task_config.tipo}")
            return False
        
        if not task_config.horario:
            logger.error("horario es requerido")
            return False
        
        # Validar formato de horario
        try:
            if ':' in task_config.horario:
                hour, minute = task_config.horario.split(':')
                if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
                    raise ValueError("Horario inválido")
        except ValueError:
            logger.error(f"Formato de horario inválido: {task_config.horario}")
            return False
        
        return True
    
    def _calculate_next_execution(self, task_config: TaskConfig) -> str:
        """Calcula la próxima ejecución de una tarea"""
        try:
            now = datetime.now()
            
            if task_config.frecuencia == "daily":
                hour, minute = map(int, task_config.horario.split(':'))
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # Si ya pasó hoy, programar para mañana
                if next_run <= now:
                    next_run += timedelta(days=1)
                    
            elif task_config.frecuencia == "hourly":
                minute = int(task_config.horario.split(':')[1]) if ':' in task_config.horario else 0
                next_run = now.replace(minute=minute, second=0, microsecond=0)
                
                # Si ya pasó esta hora, programar para la próxima
                if next_run <= now:
                    next_run += timedelta(hours=1)
                    
            elif task_config.frecuencia == "weekly":
                # Asumir que se ejecuta el mismo día de la semana
                hour, minute = map(int, task_config.horario.split(':'))
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # Si ya pasó esta semana, programar para la próxima
                if next_run <= now:
                    next_run += timedelta(weeks=1)
            else:
                # Para frecuencias custom, usar el horario como base
                hour, minute = map(int, task_config.horario.split(':'))
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                if next_run <= now:
                    next_run += timedelta(days=1)
            
            return next_run.isoformat()
            
        except Exception as e:
            logger.error(f"Error al calcular próxima ejecución: {e}")
            return (datetime.now() + timedelta(hours=1)).isoformat()
    
    def _schedule_task(self, task_config: TaskConfig):
        """Programa una tarea usando schedule"""
        try:
            if not task_config.activa:
                return
            
            if task_config.frecuencia == "daily":
                schedule.every().day.at(task_config.horario).do(
                    self._execute_task_wrapper, task_config.task_id
                ).tag(task_config.task_id)
                
            elif task_config.frecuencia == "hourly":
                minute = int(task_config.horario.split(':')[1]) if ':' in task_config.horario else 0
                schedule.every().hour.at(f":{minute:02d}").do(
                    self._execute_task_wrapper, task_config.task_id
                ).tag(task_config.task_id)
                
            elif task_config.frecuencia == "weekly":
                schedule.every().week.at(task_config.horario).do(
                    self._execute_task_wrapper, task_config.task_id
                ).tag(task_config.task_id)
            
            logger.debug(f"Tarea programada: {task_config.task_id}")
            
        except Exception as e:
            logger.error(f"Error al programar tarea {task_config.task_id}: {e}")
    
    def _execute_task_wrapper(self, task_id: str):
        """Wrapper para ejecutar tareas de forma asíncrona"""
        try:
            future = self.executor.submit(self._execute_task, task_id)
            # No esperar el resultado aquí para no bloquear el scheduler
            return future
            
        except Exception as e:
            logger.error(f"Error al ejecutar wrapper para tarea {task_id}: {e}")
    
    def _execute_task(self, task_id: str) -> TaskResult:
        """Ejecuta una tarea específica"""
        start_time = time.time()
        task_config = self.tasks.get(task_id)
        
        if not task_config:
            logger.error(f"Tarea no encontrada: {task_id}")
            return TaskResult(
                task_id=task_id,
                exito=False,
                timestamp=datetime.now().isoformat(),
                duracion_segundos=0,
                mensaje="Tarea no encontrada"
            )
        
        logger.info(f"Ejecutando tarea: {task_id} - {task_config.nombre}")
        
        try:
            # Verificar dependencias
            if not self._check_dependencies(task_config):
                raise Exception("Dependencias no satisfechas")
            
            # Obtener función para ejecutar
            task_function = self.task_functions.get(task_config.tipo)
            if not task_function:
                raise Exception(f"Función no registrada para tipo: {task_config.tipo}")
            
            # Ejecutar tarea
            resultado = task_function(**task_config.parametros)
            
            # Actualizar configuración de la tarea
            task_config.ultima_ejecucion = datetime.now().isoformat()
            task_config.reintento_actual = 0
            task_config.proxima_ejecucion = self._calculate_next_execution(task_config)
            self._save_task_to_db(task_config)
            
            # Crear resultado exitoso
            duracion = time.time() - start_time
            task_result = TaskResult(
                task_id=task_id,
                exito=True,
                timestamp=datetime.now().isoformat(),
                duracion_segundos=duracion,
                mensaje=f"Tarea ejecutada exitosamente en {duracion:.2f}s",
                datos_resultado=resultado if isinstance(resultado, dict) else {}
            )
            
            # Guardar resultado
            self._save_result_to_db(task_result)
            
            logger.info(f"Tarea completada exitosamente: {task_id}")
            return task_result
            
        except Exception as e:
            # Manejar error
            logger.error(f"Error al ejecutar tarea {task_id}: {e}")
            
            # Incrementar contador de reintentos
            task_config.reintento_actual += 1
            
            # Crear resultado de error
            duracion = time.time() - start_time
            task_result = TaskResult(
                task_id=task_id,
                exito=False,
                timestamp=datetime.now().isoformat(),
                duracion_segundos=duracion,
                mensaje=f"Error en ejecución: {str(e)}",
                error_details=str(e)
            )
            
            # Guardar resultado
            self._save_result_to_db(task_result)
            
            # Programar reintento si no se alcanzó el máximo
            if task_config.reintento_actual < task_config.reintentos_maximos:
                logger.info(f"Programando reintento para tarea {task_id} (intento {task_config.reintento_actual + 1})")
                # Programar reintento en 5 minutos
                schedule.every(5).minutes.do(
                    self._execute_task_wrapper, task_id
                ).tag(f"{task_id}_retry")
            else:
                logger.error(f"Máximo de reintentos alcanzado para tarea {task_id}")
                task_config.reintento_actual = 0  # Reset para próxima ejecución programada
            
            # Actualizar configuración
            self._save_task_to_db(task_config)
            
            return task_result
    
    def _check_dependencies(self, task_config: TaskConfig) -> bool:
        """Verifica que las dependencias de una tarea estén satisfechas"""
        if not task_config.dependencias:
            return True
        
        try:
            # Verificar que todas las dependencias se hayan ejecutado exitosamente recientemente
            for dep_task_id in task_config.dependencias:
                if not self._is_dependency_satisfied(dep_task_id):
                    logger.warning(f"Dependencia no satisfecha: {dep_task_id}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error al verificar dependencias: {e}")
            return False
    
    def _is_dependency_satisfied(self, task_id: str) -> bool:
        """Verifica si una dependencia específica está satisfecha"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Buscar la última ejecución exitosa de la dependencia
                cursor.execute('''
                    SELECT result FROM task_results 
                    WHERE task_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT 1
                ''', (task_id,))
                
                row = cursor.fetchone()
                if not row:
                    return False
                
                result_data = json.loads(row[0])
                result = TaskResult(**result_data)
                
                # Verificar que fue exitosa y reciente (últimas 24 horas)
                if not result.exito:
                    return False
                
                last_execution = datetime.fromisoformat(result.timestamp)
                if datetime.now() - last_execution > timedelta(hours=24):
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error al verificar dependencia {task_id}: {e}")
            return False
    
    def start(self):
        """Inicia el programador de tareas"""
        if self.running:
            logger.warning("El programador ya está ejecutándose")
            return
        
        logger.info("Iniciando programador de tareas...")
        
        # Programar todas las tareas activas
        for task_config in self.tasks.values():
            if task_config.activa:
                self._schedule_task(task_config)
        
        self.running = True
        
        # Iniciar thread del scheduler
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info(f"Programador iniciado con {len([t for t in self.tasks.values() if t.activa])} tareas activas")
    
    def stop(self):
        """Detiene el programador de tareas"""
        if not self.running:
            logger.warning("El programador no está ejecutándose")
            return
        
        logger.info("Deteniendo programador de tareas...")
        
        self.running = False
        
        # Limpiar schedule
        schedule.clear()
        
        # Esperar que termine el thread
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)
        
        # Cerrar executor
        self.executor.shutdown(wait=True)
        
        logger.info("Programador detenido")
    
    def _run_scheduler(self):
        """Loop principal del programador"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error en loop del programador: {e}")
                time.sleep(5)
    
    def _signal_handler(self, signum, frame):
        """Maneja señales para shutdown limpio"""
        logger.info(f"Señal recibida: {signum}")
        self.stop()
        sys.exit(0)
    
    def get_task_status(self) -> List[Dict]:
        """Obtiene el estado de todas las tareas"""
        status_list = []
        
        for task_id, task_config in self.tasks.items():
            # Obtener último resultado
            last_result = None
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT result FROM task_results 
                        WHERE task_id = ? 
                        ORDER BY created_at DESC 
                        LIMIT 1
                    ''', (task_id,))
                    
                    row = cursor.fetchone()
                    if row:
                        last_result = json.loads(row[0])
                        
            except Exception as e:
                logger.error(f"Error al obtener último resultado para {task_id}: {e}")
            
            status_list.append({
                'task_id': task_id,
                'nombre': task_config.nombre,
                'tipo': task_config.tipo,
                'activa': task_config.activa,
                'frecuencia': task_config.frecuencia,
                'horario': task_config.horario,
                'ultima_ejecucion': task_config.ultima_ejecucion,
                'proxima_ejecucion': task_config.proxima_ejecucion,
                'ultimo_resultado': last_result
            })
        
        return status_list
    
    def get_task_history(self, task_id: str, limit: int = 10) -> List[TaskResult]:
        """Obtiene el historial de ejecuciones de una tarea"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT result FROM task_results 
                    WHERE task_id = ? 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (task_id, limit))
                
                results = []
                for row in cursor.fetchall():
                    result_data = json.loads(row[0])
                    result = TaskResult(**result_data)
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Error al obtener historial de {task_id}: {e}")
            return []
    
    def execute_task_now(self, task_id: str) -> TaskResult:
        """Ejecuta una tarea inmediatamente"""
        logger.info(f"Ejecutando tarea inmediatamente: {task_id}")
        return self._execute_task(task_id)

# Funciones de utilidad para crear tareas predefinidas
def crear_tarea_scraping(task_id: str, nombre: str, horario: str, frecuencia: str = "daily", 
                        excel_path: str = "./data/competidores.xlsx") -> TaskConfig:
    """Crea una tarea de scraping de competencia"""
    return TaskConfig(
        task_id=task_id,
        nombre=nombre,
        tipo="scraping",
        frecuencia=frecuencia,
        horario=horario,
        parametros={
            "excel_path": excel_path,
            "max_posts": 3
        },
        descripcion="Scraping automático de contenido de competidores"
    )

def crear_tarea_analisis(task_id: str, nombre: str, horario: str, frecuencia: str = "daily") -> TaskConfig:
    """Crea una tarea de análisis de contenido"""
    return TaskConfig(
        task_id=task_id,
        nombre=nombre,
        tipo="analysis",
        frecuencia=frecuencia,
        horario=horario,
        parametros={},
        dependencias=["scraping_competencia"],
        descripcion="Análisis automático del contenido scrapeado"
    )

def crear_tarea_generacion_contenido(task_id: str, nombre: str, horario: str, 
                                   frecuencia: str = "daily", dias_adelante: int = 1) -> TaskConfig:
    """Crea una tarea de generación de contenido"""
    return TaskConfig(
        task_id=task_id,
        nombre=nombre,
        tipo="content_generation",
        frecuencia=frecuencia,
        horario=horario,
        parametros={
            "dias_adelante": dias_adelante
        },
        dependencias=["analisis_contenido"],
        descripcion="Generación automática de contenido basado en análisis"
    )

def crear_tarea_publicacion(task_id: str, nombre: str, horario: str, 
                           frecuencia: str = "daily", plataforma: str = "both") -> TaskConfig:
    """Crea una tarea de publicación en redes sociales"""
    return TaskConfig(
        task_id=task_id,
        nombre=nombre,
        tipo="publishing",
        frecuencia=frecuencia,
        horario=horario,
        parametros={
            "plataforma": plataforma
        },
        dependencias=["generacion_contenido"],
        descripcion="Publicación automática en redes sociales"
    )

if __name__ == "__main__":
    # Ejemplo de uso
    scheduler = TaskScheduler()
    
    # Función de ejemplo para scraping
    def ejemplo_scraping(excel_path: str, max_posts: int = 3):
        logger.info(f"Ejecutando scraping desde {excel_path}, max_posts: {max_posts}")
        time.sleep(2)  # Simular trabajo
        return {"posts_extraidos": 15, "competidores_analizados": 3}
    
    # Registrar función
    scheduler.register_task_function("scraping", ejemplo_scraping)
    
    # Crear y añadir tarea
    tarea_scraping = crear_tarea_scraping(
        "scraping_test",
        "Test Scraping",
        "14:30",
        "daily"
    )
    
    scheduler.add_task(tarea_scraping)
    
    # Mostrar estado
    status = scheduler.get_task_status()
    print("Estado de tareas:")
    for task_status in status:
        print(f"  - {task_status['nombre']}: {task_status['activa']}")
    
    # Ejecutar tarea ahora (para testing)
    print("\nEjecutando tarea de prueba...")
    resultado = scheduler.execute_task_now("scraping_test")
    print(f"Resultado: {resultado}")
    
    print("Scheduler creado exitosamente")