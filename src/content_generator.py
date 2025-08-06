"""
Módulo para generar contenido mejorado usando IA basado en el análisis de la competencia
"""

import os
import json
import random
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from loguru import logger
import openai
from openai import OpenAI
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import base64
from textwrap import wrap
import emoji

@dataclass
class GeneratedContent:
    """Clase para representar contenido generado"""
    texto: str
    hashtags: List[str]
    plataforma: str  # 'facebook' o 'instagram'
    tipo_contenido: str  # 'texto', 'imagen', 'video'
    imagen_url: Optional[str] = None
    imagen_local: Optional[str] = None
    mejor_horario: Optional[str] = None
    palabras_clave_objetivo: List[str] = None
    sentimiento_objetivo: str = "positivo"  # positivo, neutral, negativo
    engagement_esperado: Optional[float] = None
    inspiracion_competidor: Optional[str] = None
    fecha_sugerida: Optional[str] = None
    timestamp_generacion: str = ""
    
    def __post_init__(self):
        if not self.timestamp_generacion:
            self.timestamp_generacion = datetime.now().isoformat()

class ContentGenerator:
    """Generador de contenido usando IA"""
    
    def __init__(self, openai_api_key: str, brand_voice: str = "profesional_y_amigable", target_audience: str = "jóvenes_adultos_25_45"):
        """
        Inicializa el generador de contenido
        
        Args:
            openai_api_key: Clave de API de OpenAI
            brand_voice: Voz de la marca (profesional, casual, divertido, etc.)
            target_audience: Audiencia objetivo
        """
        self.client = OpenAI(api_key=openai_api_key)
        self.brand_voice = brand_voice
        self.target_audience = target_audience
        
        # Templates de prompts
        self.prompt_templates = {
            'instagram_post': """
Crea un post para Instagram dirigido a {target_audience} con voz de marca {brand_voice}.

Contexto de la competencia:
- Hashtags más usados: {hashtags_populares}
- Temas exitosos: {temas_exitosos}
- Tipo de contenido que funciona: {tipo_contenido_exitoso}
- Emojis populares: {emojis_populares}

Requisitos:
- Texto engaging de 50-150 palabras
- 5-10 hashtags relevantes
- Incluir call-to-action
- Tone: {sentimiento}
- Incorporar elementos que han funcionado para la competencia pero de forma original

Palabras clave a incluir: {palabras_clave}

Genera un post que sea mejor que la competencia pero mantenga autenticidad de marca.
""",
            
            'facebook_post': """
Crea un post para Facebook dirigido a {target_audience} con voz de marca {brand_voice}.

Contexto de la competencia:
- Hashtags más usados: {hashtags_populares}
- Temas exitosos: {temas_exitosos}  
- Tipo de contenido que funciona: {tipo_contenido_exitoso}
- Longitud promedio exitosa: {longitud_promedio} caracteres

Requisitos:
- Texto de 100-300 palabras
- 3-7 hashtags relevantes
- Incluir pregunta para generar engagement
- Tone: {sentimiento}
- Formato que invite a la conversación

Palabras clave a incluir: {palabras_clave}

Crea contenido que supere el engagement de la competencia siendo auténtico y valioso.
""",
            
            'caption_mejorado': """
Mejora este caption basándote en el análisis de la competencia exitosa:

Caption original: {caption_original}

Insights de la competencia:
- Elementos que generan más engagement: {elementos_exitosos}
- Hashtags que funcionan: {hashtags_populares}
- Estilo de escritura exitoso: {estilo_exitoso}
- Emojis efectivos: {emojis_populares}

Mejora el caption manteniendo la idea original pero aplicando las mejores prácticas observadas.
Resultado debe ser {brand_voice} y dirigido a {target_audience}.
"""
        }
        
        # Configuraciones de imagen
        self.image_templates = {
            'quote': {
                'background_colors': ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57'],
                'text_colors': ['#FFFFFF', '#2C3E50', '#34495E'],
                'fonts': ['Arial', 'Helvetica', 'Georgia']
            },
            'announcement': {
                'background_colors': ['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe'],
                'text_colors': ['#FFFFFF', '#F8F9FA'],
                'fonts': ['Arial', 'Helvetica']
            },
            'tip': {
                'background_colors': ['#43e97b', '#38f9d7', '#667eea', '#764ba2', '#f093fb'],
                'text_colors': ['#FFFFFF', '#2C3E50'],
                'fonts': ['Arial', 'Helvetica']
            }
        }
    
    def generar_contenido_instagram(self, analisis_competencia: Dict, palabras_clave: List[str] = None, sentimiento: str = "positivo") -> GeneratedContent:
        """Genera contenido optimizado para Instagram"""
        try:
            logger.info("Generando contenido para Instagram...")
            
            # Extraer insights de la competencia
            insights = self._extraer_insights_globales(analisis_competencia)
            
            # Construir prompt
            prompt = self.prompt_templates['instagram_post'].format(
                target_audience=self.target_audience,
                brand_voice=self.brand_voice,
                hashtags_populares=', '.join(insights['hashtags_populares'][:10]),
                temas_exitosos=', '.join(insights['temas_exitosos'][:5]),
                tipo_contenido_exitoso=insights['tipo_contenido_popular'],
                emojis_populares=' '.join(insights['emojis_populares'][:5]),
                sentimiento=sentimiento,
                palabras_clave=', '.join(palabras_clave) if palabras_clave else 'ninguna específica'
            )
            
            # Generar contenido con OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un experto en marketing de redes sociales especializado en crear contenido viral y engaging."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            contenido_texto = response.choices[0].message.content.strip()
            
            # Extraer hashtags del contenido generado
            hashtags = re.findall(r'#\w+', contenido_texto)
            
            # Limpiar texto (remover hashtags del final si están separados)
            texto_limpio = re.sub(r'\n\n#.*$', '', contenido_texto, flags=re.MULTILINE).strip()
            
            # Determinar mejor horario basado en análisis
            mejor_horario = self._determinar_mejor_horario(insights)
            
            # Crear contenido generado
            contenido = GeneratedContent(
                texto=texto_limpio,
                hashtags=hashtags if hashtags else self._generar_hashtags_fallback(palabras_clave),
                plataforma="instagram",
                tipo_contenido="texto",
                mejor_horario=mejor_horario,
                palabras_clave_objetivo=palabras_clave or [],
                sentimiento_objetivo=sentimiento,
                engagement_esperado=self._estimar_engagement(insights, "instagram"),
                inspiracion_competidor=self._obtener_mejor_competidor(analisis_competencia)
            )
            
            logger.info("Contenido para Instagram generado exitosamente")
            return contenido
            
        except Exception as e:
            logger.error(f"Error al generar contenido para Instagram: {e}")
            return self._generar_contenido_fallback("instagram", palabras_clave, sentimiento)
    
    def generar_contenido_facebook(self, analisis_competencia: Dict, palabras_clave: List[str] = None, sentimiento: str = "positivo") -> GeneratedContent:
        """Genera contenido optimizado para Facebook"""
        try:
            logger.info("Generando contenido para Facebook...")
            
            # Extraer insights de la competencia
            insights = self._extraer_insights_globales(analisis_competencia)
            
            # Construir prompt
            prompt = self.prompt_templates['facebook_post'].format(
                target_audience=self.target_audience,
                brand_voice=self.brand_voice,
                hashtags_populares=', '.join(insights['hashtags_populares'][:10]),
                temas_exitosos=', '.join(insights['temas_exitosos'][:5]),
                tipo_contenido_exitoso=insights['tipo_contenido_popular'],
                longitud_promedio=insights['longitud_promedio'],
                sentimiento=sentimiento,
                palabras_clave=', '.join(palabras_clave) if palabras_clave else 'ninguna específica'
            )
            
            # Generar contenido con OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un experto en marketing de redes sociales especializado en crear contenido engaging para Facebook."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,
                temperature=0.7
            )
            
            contenido_texto = response.choices[0].message.content.strip()
            
            # Extraer hashtags del contenido generado
            hashtags = re.findall(r'#\w+', contenido_texto)
            
            # Limpiar texto
            texto_limpio = re.sub(r'\n\n#.*$', '', contenido_texto, flags=re.MULTILINE).strip()
            
            # Determinar mejor horario
            mejor_horario = self._determinar_mejor_horario(insights)
            
            contenido = GeneratedContent(
                texto=texto_limpio,
                hashtags=hashtags if hashtags else self._generar_hashtags_fallback(palabras_clave),
                plataforma="facebook",
                tipo_contenido="texto",
                mejor_horario=mejor_horario,
                palabras_clave_objetivo=palabras_clave or [],
                sentimiento_objetivo=sentimiento,
                engagement_esperado=self._estimar_engagement(insights, "facebook"),
                inspiracion_competidor=self._obtener_mejor_competidor(analisis_competencia)
            )
            
            logger.info("Contenido para Facebook generado exitosamente")
            return contenido
            
        except Exception as e:
            logger.error(f"Error al generar contenido para Facebook: {e}")
            return self._generar_contenido_fallback("facebook", palabras_clave, sentimiento)
    
    def mejorar_caption_existente(self, caption_original: str, analisis_competencia: Dict, plataforma: str = "instagram") -> GeneratedContent:
        """Mejora un caption existente basándose en el análisis de competencia"""
        try:
            logger.info(f"Mejorando caption para {plataforma}...")
            
            insights = self._extraer_insights_globales(analisis_competencia)
            
            prompt = self.prompt_templates['caption_mejorado'].format(
                caption_original=caption_original,
                elementos_exitosos=', '.join(insights['elementos_exitosos'][:5]),
                hashtags_populares=', '.join(insights['hashtags_populares'][:8]),
                estilo_exitoso=insights['estilo_escritura'],
                emojis_populares=' '.join(insights['emojis_populares'][:5]),
                brand_voice=self.brand_voice,
                target_audience=self.target_audience
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un experto en optimización de contenido para redes sociales."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=400,
                temperature=0.7
            )
            
            contenido_mejorado = response.choices[0].message.content.strip()
            hashtags = re.findall(r'#\w+', contenido_mejorado)
            texto_limpio = re.sub(r'\n\n#.*$', '', contenido_mejorado, flags=re.MULTILINE).strip()
            
            return GeneratedContent(
                texto=texto_limpio,
                hashtags=hashtags,
                plataforma=plataforma,
                tipo_contenido="texto",
                mejor_horario=self._determinar_mejor_horario(insights),
                sentimiento_objetivo="positivo",
                inspiracion_competidor=self._obtener_mejor_competidor(analisis_competencia)
            )
            
        except Exception as e:
            logger.error(f"Error al mejorar caption: {e}")
            return self._generar_contenido_fallback(plataforma, [], "positivo")
    
    def generar_imagen_texto(self, texto: str, tipo_imagen: str = "quote", output_path: str = None) -> Optional[str]:
        """Genera una imagen con texto usando PIL"""
        try:
            logger.info(f"Generando imagen tipo '{tipo_imagen}'...")
            
            # Configuración del template
            template = self.image_templates.get(tipo_imagen, self.image_templates['quote'])
            
            # Dimensiones de la imagen
            width, height = 1080, 1080  # Formato cuadrado para Instagram
            
            # Crear imagen
            background_color = random.choice(template['background_colors'])
            img = Image.new('RGB', (width, height), color=background_color)
            draw = ImageDraw.Draw(img)
            
            # Configurar fuente (usar fuente por defecto si no se encuentra la específica)
            try:
                font_size = 48
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                try:
                    font = ImageFont.load_default()
                    font_size = 36
                except:
                    logger.warning("No se pudo cargar fuente, usando fuente por defecto")
                    font = None
                    font_size = 30
            
            # Preparar texto (dividir en líneas)
            max_chars_per_line = 25
            lines = wrap(texto, max_chars_per_line)
            
            # Calcular posición del texto
            total_text_height = len(lines) * font_size + (len(lines) - 1) * 10
            start_y = (height - total_text_height) // 2
            
            # Dibujar texto
            text_color = random.choice(template['text_colors'])
            
            for i, line in enumerate(lines):
                # Centrar cada línea
                if font:
                    text_width = draw.textlength(line, font=font)
                else:
                    text_width = len(line) * 20  # Estimación
                
                x = (width - text_width) // 2
                y = start_y + i * (font_size + 10)
                
                if font:
                    draw.text((x, y), line, fill=text_color, font=font)
                else:
                    draw.text((x, y), line, fill=text_color)
            
            # Guardar imagen
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"./generated_content/imagen_{tipo_imagen}_{timestamp}.png"
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            img.save(output_path, "PNG", quality=95)
            logger.info(f"Imagen generada: {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error al generar imagen: {e}")
            return None
    
    def generar_contenido_programado(self, analisis_competencia: Dict, dias_adelante: int = 7) -> List[GeneratedContent]:
        """Genera contenido programado para varios días"""
        contenidos = []
        
        try:
            logger.info(f"Generando contenido programado para {dias_adelante} días...")
            
            # Horarios predefinidos basados en mejores prácticas
            horarios_instagram = ["09:00", "14:00", "19:00"]  # 3 veces al día
            horarios_facebook = ["09:00"]  # 1 vez al día
            
            # Temas y palabras clave variadas
            temas_contenido = [
                {"tema": "motivación", "palabras": ["éxito", "crecimiento", "objetivos"]},
                {"tema": "tips", "palabras": ["consejo", "productividad", "eficiencia"]},
                {"tema": "producto", "palabras": ["calidad", "innovación", "beneficios"]},
                {"tema": "comunidad", "palabras": ["equipo", "clientes", "experiencia"]},
                {"tema": "inspiración", "palabras": ["visión", "futuro", "cambio"]},
                {"tema": "educativo", "palabras": ["aprender", "conocimiento", "información"]},
                {"tema": "detrás_escenas", "palabras": ["proceso", "trabajo", "dedicación"]}
            ]
            
            fecha_inicio = datetime.now()
            
            for dia in range(dias_adelante):
                fecha_actual = fecha_inicio + timedelta(days=dia)
                
                # Contenido para Instagram (3 veces al día)
                for i, horario in enumerate(horarios_instagram):
                    tema = random.choice(temas_contenido)
                    
                    contenido_ig = self.generar_contenido_instagram(
                        analisis_competencia,
                        palabras_clave=tema["palabras"],
                        sentimiento="positivo"
                    )
                    
                    # Configurar fecha y horario
                    fecha_publicacion = fecha_actual.replace(
                        hour=int(horario.split(":")[0]),
                        minute=int(horario.split(":")[1]),
                        second=0,
                        microsecond=0
                    )
                    
                    contenido_ig.fecha_sugerida = fecha_publicacion.isoformat()
                    contenidos.append(contenido_ig)
                
                # Contenido para Facebook (1 vez al día)
                for horario in horarios_facebook:
                    tema = random.choice(temas_contenido)
                    
                    contenido_fb = self.generar_contenido_facebook(
                        analisis_competencia,
                        palabras_clave=tema["palabras"],
                        sentimiento="positivo"
                    )
                    
                    fecha_publicacion = fecha_actual.replace(
                        hour=int(horario.split(":")[0]),
                        minute=int(horario.split(":")[1]),
                        second=0,
                        microsecond=0
                    )
                    
                    contenido_fb.fecha_sugerida = fecha_publicacion.isoformat()
                    contenidos.append(contenido_fb)
            
            logger.info(f"Generados {len(contenidos)} contenidos programados")
            return contenidos
            
        except Exception as e:
            logger.error(f"Error al generar contenido programado: {e}")
            return []
    
    def _extraer_insights_globales(self, analisis_competencia: Dict) -> Dict:
        """Extrae insights globales de todos los competidores"""
        insights = {
            'hashtags_populares': [],
            'temas_exitosos': [],
            'tipo_contenido_popular': 'texto',
            'emojis_populares': [],
            'longitud_promedio': 100,
            'elementos_exitosos': [],
            'estilo_escritura': 'informal y cercano'
        }
        
        try:
            if 'analisis_individual' in analisis_competencia:
                # Agregr todos los hashtags
                all_hashtags = []
                all_temas = []
                all_emojis = []
                longitudes = []
                tipos_contenido = {}
                
                for nombre, analisis in analisis_competencia['analisis_individual'].items():
                    # Hashtags
                    if hasattr(analisis, 'insights') and hasattr(analisis.insights, 'hashtags_mas_usados'):
                        for hashtag, count in analisis.insights.hashtags_mas_usados:
                            all_hashtags.extend([hashtag] * count)
                    
                    # Temas
                    if hasattr(analisis, 'insights') and hasattr(analisis.insights, 'temas_principales'):
                        all_temas.extend(analisis.insights.temas_principales)
                    
                    # Emojis
                    if hasattr(analisis, 'insights') and hasattr(analisis.insights, 'emojis_mas_usados'):
                        for emoji_char, count in analisis.insights.emojis_mas_usados:
                            all_emojis.extend([emoji_char] * count)
                    
                    # Longitud promedio
                    if hasattr(analisis, 'insights') and hasattr(analisis.insights, 'longitud_promedio_texto'):
                        longitudes.append(analisis.insights.longitud_promedio_texto)
                    
                    # Tipos de contenido
                    if hasattr(analisis, 'insights') and hasattr(analisis.insights, 'tipos_contenido'):
                        for tipo, count in analisis.insights.tipos_contenido.items():
                            tipos_contenido[tipo] = tipos_contenido.get(tipo, 0) + count
                
                # Procesar resultados
                from collections import Counter
                
                hashtag_counter = Counter(all_hashtags)
                insights['hashtags_populares'] = [tag for tag, _ in hashtag_counter.most_common(15)]
                
                tema_counter = Counter(all_temas)
                insights['temas_exitosos'] = [tema for tema, _ in tema_counter.most_common(10)]
                
                emoji_counter = Counter(all_emojis)
                insights['emojis_populares'] = [emoji_char for emoji_char, _ in emoji_counter.most_common(10)]
                
                if longitudes:
                    insights['longitud_promedio'] = int(sum(longitudes) / len(longitudes))
                
                if tipos_contenido:
                    insights['tipo_contenido_popular'] = max(tipos_contenido, key=tipos_contenido.get)
                
                # Elementos de éxito genéricos
                insights['elementos_exitosos'] = [
                    'preguntas directas', 'llamadas a la acción', 'emojis', 
                    'hashtags relevantes', 'contenido visual', 'historias personales'
                ]
        
        except Exception as e:
            logger.warning(f"Error al extraer insights globales: {e}")
        
        return insights
    
    def _determinar_mejor_horario(self, insights: Dict) -> str:
        """Determina el mejor horario basado en insights"""
        # Horarios por defecto si no hay datos específicos
        horarios_default = {
            'Mañana (6-12h)': "09:00",
            'Tarde (12-18h)': "14:00", 
            'Noche (18-24h)': "19:00",
            'Madrugada (0-6h)': "08:00"
        }
        
        # Si hay datos de horarios en insights, usar el mejor
        # Por ahora retornar horario por defecto popular
        return "14:00"  # Tarde suele ser buen horario universal
    
    def _estimar_engagement(self, insights: Dict, plataforma: str) -> float:
        """Estima engagement esperado basado en insights"""
        # Estimación básica - en producción se podría usar ML
        base_engagement = 50.0 if plataforma == "instagram" else 30.0
        
        # Ajustar basado en factores conocidos
        if insights.get('hashtags_populares'):
            base_engagement *= 1.2
        
        if insights.get('emojis_populares'):
            base_engagement *= 1.1
        
        return round(base_engagement, 1)
    
    def _obtener_mejor_competidor(self, analisis_competencia: Dict) -> Optional[str]:
        """Obtiene el nombre del competidor con mejor engagement"""
        try:
            if 'analisis_individual' not in analisis_competencia:
                return None
            
            mejor_competidor = None
            mejor_engagement = 0
            
            for nombre, analisis in analisis_competencia['analisis_individual'].items():
                if (hasattr(analisis, 'insights') and 
                    hasattr(analisis.insights, 'patrones_engagement') and
                    'engagement_rate' in analisis.insights.patrones_engagement):
                    
                    engagement = analisis.insights.patrones_engagement['engagement_rate']
                    if engagement > mejor_engagement:
                        mejor_engagement = engagement
                        mejor_competidor = nombre
            
            return mejor_competidor
            
        except Exception as e:
            logger.warning(f"Error al obtener mejor competidor: {e}")
            return None
    
    def _generar_hashtags_fallback(self, palabras_clave: List[str] = None) -> List[str]:
        """Genera hashtags de respaldo si falla la generación principal"""
        hashtags_genericos = [
            "#marketing", "#contenido", "#social", "#digital", 
            "#negocio", "#emprendimiento", "#inspiracion", "#tips"
        ]
        
        hashtags_resultado = hashtags_genericos[:5]
        
        if palabras_clave:
            for palabra in palabras_clave[:3]:
                hashtags_resultado.append(f"#{palabra.lower().replace(' ', '')}")
        
        return hashtags_resultado
    
    def _generar_contenido_fallback(self, plataforma: str, palabras_clave: List[str] = None, sentimiento: str = "positivo") -> GeneratedContent:
        """Genera contenido de respaldo cuando falla la generación principal"""
        
        textos_fallback = {
            "instagram": [
                "✨ Descubre nuevas oportunidades cada día ✨\n\n¿Qué te inspira a seguir adelante?\n\n#inspiracion #crecimiento #oportunidades",
                "🚀 El éxito está en los pequeños pasos diarios 🚀\n\n¿Cuál fue tu logro de hoy?\n\n#exito #progreso #meta",
                "💡 Compartiendo valor, creando comunidad 💡\n\n¿Qué consejo compartirías con nuestra comunidad?\n\n#comunidad #valor #consejos"
            ],
            "facebook": [
                "Queremos compartir algo especial con nuestra comunidad...\n\nCada día trabajamos para ofrecer lo mejor, y queremos conocer tu opinión: ¿qué es lo que más valoras en una marca?\n\nTus comentarios nos ayudan a crecer juntos. 💬\n\n#comunidad #valor #opinion",
                "¡Reflexión del día! 🌟\n\nEl crecimiento no es solo individual, es colectivo. Cuando una persona de nuestra comunidad crece, todos crecemos.\n\n¿Qué has aprendido recientemente que te gustaría compartir?\n\n#crecimiento #comunidad #aprendizaje",
                "Detrás de cada gran resultado hay pequeños esfuerzos diarios. 💪\n\nHoy queremos reconocer el trabajo constante que hace cada uno para alcanzar sus metas.\n\n¿Cuál es tu pequeño paso de hoy hacia tu gran objetivo?\n\n#esfuerzo #constancia #metas"
            ]
        }
        
        texto = random.choice(textos_fallback.get(plataforma, textos_fallback["instagram"]))
        hashtags = re.findall(r'#\w+', texto)
        texto_limpio = re.sub(r'#\w+', '', texto).strip()
        
        return GeneratedContent(
            texto=texto_limpio,
            hashtags=hashtags,
            plataforma=plataforma,
            tipo_contenido="texto",
            palabras_clave_objetivo=palabras_clave or [],
            sentimiento_objetivo=sentimiento
        )
    
    def guardar_contenido_generado(self, contenidos: List[GeneratedContent], filepath: str):
        """Guarda contenido generado en archivo JSON"""
        try:
            contenidos_dict = [asdict(contenido) for contenido in contenidos]
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(contenidos_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Contenido guardado en: {filepath}")
            
        except Exception as e:
            logger.error(f"Error al guardar contenido: {e}")
    
    def cargar_contenido_generado(self, filepath: str) -> List[GeneratedContent]:
        """Carga contenido desde archivo JSON"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                contenidos_dict = json.load(f)
            
            contenidos = []
            for contenido_data in contenidos_dict:
                contenido = GeneratedContent(**contenido_data)
                contenidos.append(contenido)
            
            logger.info(f"Cargados {len(contenidos)} contenidos desde: {filepath}")
            return contenidos
            
        except Exception as e:
            logger.error(f"Error al cargar contenido: {e}")
            return []

# Función de utilidad
def generar_campana_completa(analisis_competencia: Dict, openai_api_key: str, dias: int = 7) -> List[GeneratedContent]:
    """Función de conveniencia para generar una campaña completa"""
    generator = ContentGenerator(openai_api_key)
    return generator.generar_contenido_programado(analisis_competencia, dias)

if __name__ == "__main__":
    # Ejemplo de uso
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Simular análisis de competencia
    analisis_ejemplo = {
        'analisis_individual': {
            'Competidor1': type('obj', (object,), {
                'insights': type('insights', (object,), {
                    'hashtags_mas_usados': [('#marketing', 5), ('#digital', 3)],
                    'temas_principales': ['tecnología', 'innovación'],
                    'emojis_mas_usados': [('🚀', 3), ('💡', 2)],
                    'longitud_promedio_texto': 120,
                    'tipos_contenido': {'imagen': 5, 'texto': 3}
                })()
            })()
        }
    }
    
    # Crear generador
    api_key = os.getenv('OPENAI_API_KEY', 'sk-test-key')
    generator = ContentGenerator(api_key)
    
    # Generar contenido
    contenido_ig = generator.generar_contenido_instagram(analisis_ejemplo, ['innovación', 'tecnología'])
    contenido_fb = generator.generar_contenido_facebook(analisis_ejemplo, ['marketing', 'digital'])
    
    print("=== CONTENIDO INSTAGRAM ===")
    print(f"Texto: {contenido_ig.texto}")
    print(f"Hashtags: {contenido_ig.hashtags}")
    print(f"Mejor horario: {contenido_ig.mejor_horario}")
    
    print("\n=== CONTENIDO FACEBOOK ===")
    print(f"Texto: {contenido_fb.texto}")
    print(f"Hashtags: {contenido_fb.hashtags}")
    print(f"Mejor horario: {contenido_fb.mejor_horario}")