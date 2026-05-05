import streamlit as st
import os
import re
import random
import asyncio
import edge_tts
import glob
import base64
from groq import Groq
from pydub import AudioSegment
from gtts import gTTS

# --- CONFIGURACIÓN TÉCNICA ---
#AudioSegment.converter = "ffmpeg.exe"
AudioSegment.ffprobe = "ffprobe.exe"

st.set_page_config(page_title="Trucker English Editor", page_icon="🚛", layout="centered")

# --- MEMORIA DE SESIÓN (Para no perder cambios al recargar) ---
if 'lista_palabras' not in st.session_state:
    st.session_state.lista_palabras = """axle, beams, binder, box, BOL, bill of lading, inspection bay, lot, Mud flaps, parking space, pull-off, unload, brake, cab, cab card, CDL, medical card, logs, ELD, status, on-duty, off-duty, driving, permit, pull over, back up, keep going, slow down, arrow, flat, leaking, smoke, bulbs, lights, registration, insurance, charged, chassis, check, clean, clear, commercial, compliance, compliant, container, cracked, cracks, cuts, damage, DVIR, DOT, emergency, equipment, extinguisher, fifth-wheel, fine, fire, fluid, flush, fuses, gauge, glass, glove, high beams, low beams, horn, hours of service, identification, inspect, landing-gear, leaks, license, locked, mirror, paperwork, alcohol, drugs, substances, pressure, pre-trip, properly, release, reverse, rims, roadside, running, seatbelt, secured, sidewall, signs, signal, spare, step, tandem, tire, trailer, transmit, tread, triangles, truck, unit, valid, vehicle, washer, windshield, wipers, work, weight station"""

if 'prompt_maestro' not in st.session_state:
    st.session_state.prompt_maestro = """Actúa como un oficial del DOT real en una inspección de carretera. 
Tu objetivo: Crear bloques de práctica siguiendo un patrón ESTRICTO.

REGLAS DE ORO:
1. Vocabulario: Usa palabras de la lista proporcionada.
2. Estilo: Inglés directo, seco y rápido.
3. SECUENCIA OBLIGATORIA (No puedes saltarte el orden):
   Bloque 1: Pregunta (Question)
   Bloque 2: Indicación/Comando (Command)
   Bloque 3: Advertencia (Warning)
   Bloque 4: Hallazgo (Finding)
   ... y repetir el ciclo (1, 2, 3, 4, 1, 2...).

EJEMPLOS DE ESTILO (SOLO REFERENCIA, PROHIBIDO USAR ESTAS FRASES):
- Pregunta: "Show me your CDL and medical card."
- Comando: "Step out of the cab now."
- Advertencia: "Your tire tread is getting low, watch it."
- Hallazgo: "I found a leak in your secondary air system."

REGLA ANTI-REPETICIÓN: Genera frases totalmente nuevas y aleatorias usando la lista de palabras. No empieces siempre con las mismas órdenes.

FORMATO DE SALIDA (Usa exactamente '###' para separar bloques):
ES: [Frase en español]
EN: [Frase del oficial]
RES: [Respuesta del camionero, máx 4 palabras]
###"""


# --- CONFIGURACIÓN API (MODIFICADO ÚNICAMENTE PARA SECRETOS) ---
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    st.error("Error: No se encontró GROQ_API_KEY en los secretos de Streamlit.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)
MODELO_ACTUAL = "llama-3.3-70b-versatile"
#MODELO_ACTUAL = "llama-3.1-8b-instant"

async def generate_edge_audio(text, voice, filename):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

# --- INTERFAZ ---
st.title("🚛 Trucker English Pro")

# --- BLOQUE DE EDICIÓN (EXPANDER) ---
with st.expander("⚙️ Editar Lista de Palabras y Prompt"):
    st.session_state.lista_palabras = st.text_area(
        "Tu Lista de Vocabulario:", 
        value=st.session_state.lista_palabras, 
        height=200
    )
    st.session_state.prompt_maestro = st.text_area(
        "Instrucciones para la IA (Prompt):", 
        value=st.session_state.prompt_maestro, 
        height=150
    )
    st.info("Cualquier cambio aquí se aplicará en la siguiente generación.")

# --- GENERACIÓN ---
cantidad = st.slider("Frases a generar", 1, 15, 5)

if st.button("🚀 Generar Lecciones", use_container_width=True):
    # Limpiar archivos viejos
    for f in glob.glob("leccion_*.mp3"):
        try: os.remove(f)
        except: pass
    
    # --- LÓGICA DE SELECCIÓN ALEATORIA (SOLO 60 PALABRAS) ---
    palabras_full = [p.strip() for p in st.session_state.lista_palabras.split(',') if p.strip()]
    palabras_seleccionadas = random.sample(palabras_full, min(len(palabras_full), 60))
    lista_para_api = ", ".join(palabras_seleccionadas)
    
    seed = random.randint(1, 100000)
    
    # Construcción dinámica del prompt usando solo las 60 palabras seleccionadas
    prompt_final = f"""
    {st.session_state.prompt_maestro}
    CANTIDAD: {cantidad} bloques.
    REGLA: Usa separador '###'.
    
LISTA DE PALABRAS (Prioridad): {lista_para_api}

RECUERDA: Empieza con Pregunta, luego Comando, luego Advertencia, luego Hallazgo. 
PROHIBIDO generar dos preguntas seguidas.

    FORMATO:
    ES: [frase en español]
    EN: EN: [frase del oficial en inglés según el tipo: pregunta, comando, advertencia o hallazgo]
    RES: [respuesta corta en inglés]
    
    PALABRAS CLAVE PARA USAR: {lista_para_api}
    ID de variación: {seed}
    """

    try:
        with st.spinner("IA grabando audios..."):
            completion = client.chat.completions.create(
                model=MODELO_ACTUAL,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a strict DOT inspector. You MUST follow the requested pattern (Question, Command, Warning, Finding) without exception. Do not repeat types. Be dry and direct."
                    },
                    {
                        "role": "user", 
                        "content": prompt_final
                    }
                ],
                temperature=0.7
            )

            # --- 1. PROCESAMIENTO DE TEXTO ---
            texto_ia = completion.choices[0].message.content
            bloques = [b for b in texto_ia.split('###') if "EN:" in b]

            # --- 2. DEFINICIÓN DE VOCES (IMPORTANTE: Debe estar aquí arriba) ---
            voces_maestras = [
                'en-US-AndrewNeural', 'en-US-BrianNeural', 'en-US-ChristopherNeural', 
                'en-US-EricNeural', 'en-US-GuyNeural', 'en-US-JennyNeural', 
                'en-US-AvaNeural', 'en-US-MichelleNeural', 'en-GB-SoniaNeural', 
                'en-GB-RyanNeural', 'en-AU-WilliamNeural', 'en-CA-LiamNeural'
            ]

            # --- 3. BUCLE PRINCIPAL DE LECCIONES ---
            for i, bloque in enumerate(bloques):
                es_m = re.search(r"ES:(.*)", bloque)
                en_m = re.search(r"EN:(.*)", bloque)
                res_m = re.search(r"RES:(.*)", bloque)

                if es_m and en_m and res_m:
                    es_t, en_t, res_t = es_m.group(1).strip(), en_m.group(1).strip(), res_m.group(1).strip()
                    
                    st.subheader(f"Lección {i+1}")
                    st.write(f"🇪🇸 {es_t}")
                    st.write(f"🇺🇸 **{en_t}** | *{res_t}*")

                    # Audio en español
                    gTTS(es_t, lang='es').save("es.mp3")
                    a_es = AudioSegment.from_mp3("es.mp3")
                    pausa = AudioSegment.silent(duration=1000)

                    # Seleccionamos las 5 voces (Aquí es donde daba el error)
                    voces_leccion = random.sample(voces_maestras, 5)
                    
                    audio_preguntas = AudioSegment.empty()
                    audio_respuestas = AudioSegment.empty()

                    # --- BUCLE INTERNO: EL OFICIAL REPITE, EL CAMIONERO NO ---
                    for v_idx, voz_elegida in enumerate(voces_leccion):
                        f_q = f"q_{v_idx}.mp3"
                        f_a = "res_camionero.mp3" # Nombre fijo para la respuesta
                        
                        # 1. OFICIAL: Se graban las 5 voces distintas
                        asyncio.run(generate_edge_audio(en_t, voz_elegida, f_q))
                        audio_preguntas += AudioSegment.from_mp3(f_q) + pausa
                        
                        # 2. CAMIONERO: Grabamos solo una vez (en la primera vuelta)
                        if v_idx == 0:
                            asyncio.run(generate_edge_audio(res_t, voz_elegida, f_a))
                        
                        # 3. CAMIONERO: Añadimos el audio a la cadena solo 3 veces
                        if v_idx < 3:
                            audio_respuestas += AudioSegment.from_mp3(f_a) + pausa

                    # Unión final de la lección
                    final = a_es + pausa + audio_preguntas + audio_respuestas
                    
                    audio_path = f"leccion_{i}.mp3"
                    final.export(audio_path, format="mp3")
                    st.audio(audio_path)

    except Exception as e:
        st.error(f"Error: {e}")

# --- REPRODUCTOR MAESTRO ---
def mostrar_reproductor_bucle():
    archivos = glob.glob("leccion_*.mp3")
    if not archivos: return
    archivos.sort(key=lambda x: int(re.search(r'\d+', x).group()))

    st.divider()
    if st.button("🎧 Activar Bucle Maestro", use_container_width=True):
        with st.spinner("Uniendo..."):
            playlist = AudioSegment.empty()
            pausa_p = AudioSegment.silent(duration=2500)
            for f in archivos:
                playlist += AudioSegment.from_mp3(f) + pausa_p
            
            playlist.export("master.mp3", format="mp3")
            with open("master.mp3", "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            
            st.markdown(f"""
                <div style="text-align:center; background:#262730; padding:20px; border-radius:10px; border:2px solid #4CAF50;">
                    <h3 style="color:#4CAF50;">Modo Camionero Activo</h3>
                    <audio controls loop autoplay style="width:100%;">
                        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                    </audio>
                </div>
            """, unsafe_allow_html=True)

mostrar_reproductor_bucle()
