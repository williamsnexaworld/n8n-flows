"""
Módulo para leer y gestionar la lista de competidores desde Excel
"""

import pandas as pd
import os
from typing import List, Dict, Optional
from loguru import logger
import openpyxl
from dataclasses import dataclass

@dataclass
class Competidor:
    """Clase para representar un competidor"""
    nombre: str
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    sector: Optional[str] = None
    activo: bool = True
    notas: Optional[str] = None

class ExcelReader:
    """Clase para leer y gestionar competidores desde Excel"""
    
    def __init__(self, excel_path: str):
        self.excel_path = excel_path
        self.competidores: List[Competidor] = []
        
    def crear_excel_ejemplo(self) -> None:
        """Crea un archivo Excel de ejemplo con la estructura esperada"""
        try:
            # Datos de ejemplo
            datos_ejemplo = {
                'Nombre': [
                    'Competidor 1',
                    'Competidor 2', 
                    'Competidor 3'
                ],
                'Facebook_URL': [
                    'https://facebook.com/competidor1',
                    'https://facebook.com/competidor2',
                    'https://facebook.com/competidor3'
                ],
                'Instagram_URL': [
                    'https://instagram.com/competidor1',
                    'https://instagram.com/competidor2',
                    'https://instagram.com/competidor3'
                ],
                'Sector': [
                    'Tecnología',
                    'Moda',
                    'Alimentación'
                ],
                'Activo': [
                    True,
                    True,
                    False
                ],
                'Notas': [
                    'Publican mucho contenido técnico',
                    'Excelente uso de hashtags',
                    'Pausado temporalmente'
                ]
            }
            
            df = pd.DataFrame(datos_ejemplo)
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(self.excel_path), exist_ok=True)
            
            # Guardar con formato Excel
            with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Competidores', index=False)
                
                # Dar formato a la hoja
                workbook = writer.book
                worksheet = writer.sheets['Competidores']
                
                # Ajustar ancho de columnas
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            logger.info(f"Archivo Excel de ejemplo creado en: {self.excel_path}")
            
        except Exception as e:
            logger.error(f"Error al crear archivo Excel de ejemplo: {e}")
            raise
    
    def leer_competidores(self) -> List[Competidor]:
        """Lee la lista de competidores desde el archivo Excel"""
        try:
            if not os.path.exists(self.excel_path):
                logger.warning(f"Archivo Excel no encontrado: {self.excel_path}")
                logger.info("Creando archivo de ejemplo...")
                self.crear_excel_ejemplo()
                return []
            
            # Leer Excel
            df = pd.read_excel(self.excel_path, sheet_name='Competidores')
            
            # Validar columnas requeridas
            columnas_requeridas = ['Nombre']
            columnas_opcionales = ['Facebook_URL', 'Instagram_URL', 'Sector', 'Activo', 'Notas']
            
            for col in columnas_requeridas:
                if col not in df.columns:
                    raise ValueError(f"Columna requerida '{col}' no encontrada en el Excel")
            
            # Agregar columnas opcionales si no existen
            for col in columnas_opcionales:
                if col not in df.columns:
                    df[col] = None
            
            # Convertir a objetos Competidor
            competidores = []
            for _, row in df.iterrows():
                competidor = Competidor(
                    nombre=str(row['Nombre']).strip(),
                    facebook_url=self._limpiar_url(row.get('Facebook_URL')),
                    instagram_url=self._limpiar_url(row.get('Instagram_URL')),
                    sector=str(row.get('Sector', '')).strip() if pd.notna(row.get('Sector')) else None,
                    activo=bool(row.get('Activo', True)),
                    notas=str(row.get('Notas', '')).strip() if pd.notna(row.get('Notas')) else None
                )
                
                # Solo agregar si tiene al menos una URL válida
                if competidor.facebook_url or competidor.instagram_url:
                    competidores.append(competidor)
                else:
                    logger.warning(f"Competidor '{competidor.nombre}' omitido - sin URLs válidas")
            
            self.competidores = competidores
            logger.info(f"Cargados {len(competidores)} competidores desde Excel")
            
            return competidores
            
        except Exception as e:
            logger.error(f"Error al leer archivo Excel: {e}")
            raise
    
    def _limpiar_url(self, url) -> Optional[str]:
        """Limpia y valida URLs"""
        if pd.isna(url) or not url:
            return None
        
        url = str(url).strip()
        if not url or url.lower() in ['nan', 'none', '']:
            return None
        
        # Agregar https:// si no lo tiene
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        return url
    
    def obtener_competidores_activos(self) -> List[Competidor]:
        """Obtiene solo los competidores marcados como activos"""
        return [comp for comp in self.competidores if comp.activo]
    
    def obtener_urls_facebook(self) -> List[str]:
        """Obtiene todas las URLs de Facebook de competidores activos"""
        urls = []
        for comp in self.obtener_competidores_activos():
            if comp.facebook_url:
                urls.append(comp.facebook_url)
        return urls
    
    def obtener_urls_instagram(self) -> List[str]:
        """Obtiene todas las URLs de Instagram de competidores activos"""
        urls = []
        for comp in self.obtener_competidores_activos():
            if comp.instagram_url:
                urls.append(comp.instagram_url)
        return urls
    
    def buscar_por_nombre(self, nombre: str) -> Optional[Competidor]:
        """Busca un competidor por nombre"""
        for comp in self.competidores:
            if comp.nombre.lower() == nombre.lower():
                return comp
        return None
    
    def estadisticas(self) -> Dict:
        """Obtiene estadísticas de los competidores"""
        total = len(self.competidores)
        activos = len(self.obtener_competidores_activos())
        con_facebook = len([c for c in self.competidores if c.facebook_url])
        con_instagram = len([c for c in self.competidores if c.instagram_url])
        
        return {
            'total_competidores': total,
            'competidores_activos': activos,
            'con_facebook': con_facebook,
            'con_instagram': con_instagram,
            'sectores': list(set([c.sector for c in self.competidores if c.sector]))
        }
    
    def actualizar_estado_competidor(self, nombre: str, activo: bool) -> bool:
        """Actualiza el estado activo/inactivo de un competidor"""
        try:
            # Leer Excel actual
            df = pd.read_excel(self.excel_path, sheet_name='Competidores')
            
            # Encontrar y actualizar
            mask = df['Nombre'].str.lower() == nombre.lower()
            if mask.any():
                df.loc[mask, 'Activo'] = activo
                
                # Guardar cambios
                with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Competidores', index=False)
                
                # Recargar competidores
                self.leer_competidores()
                
                logger.info(f"Estado de '{nombre}' actualizado a: {activo}")
                return True
            else:
                logger.warning(f"Competidor '{nombre}' no encontrado")
                return False
                
        except Exception as e:
            logger.error(f"Error al actualizar estado de competidor: {e}")
            return False

# Función de utilidad para usar desde otros módulos
def cargar_competidores(excel_path: str) -> List[Competidor]:
    """Función de conveniencia para cargar competidores"""
    reader = ExcelReader(excel_path)
    return reader.leer_competidores()

if __name__ == "__main__":
    # Ejemplo de uso
    excel_path = "../data/competidores.xlsx"
    reader = ExcelReader(excel_path)
    
    # Crear archivo de ejemplo si no existe
    if not os.path.exists(excel_path):
        reader.crear_excel_ejemplo()
    
    # Cargar competidores
    competidores = reader.leer_competidores()
    
    # Mostrar estadísticas
    stats = reader.estadisticas()
    print("Estadísticas de competidores:")
    for key, value in stats.items():
        print(f"  {key}: {value}")