import logging
import os
from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
    metrics,
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import openai, deepgram, silero, turn_detector
from twilio.twiml.voice_response import VoiceResponse
from dataclasses import dataclass, asdict
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import re
from datetime import datetime
import random

load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("voice-agent")


# This data can be stored on AWS DynamoDB as documents. 
@dataclass
class PatientInfo:
    name: Optional[str] = None
    dob: Optional[str] = None
    insurance_payer: Optional[str] = None
    insurance_id: Optional[str] = None
    referral: Optional[bool] = None
    referral_physician: Optional[str] = None
    chief_complaint: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    appointment_time: Optional[str] = None
    appointment_doctor: Optional[str] = None

patient_info = PatientInfo()

doctors = [
    {"name": "Dr. Emily Carter", "specialty": "Cardiology"},
    {"name": "Dr. Michael Smith", "specialty": "Dermatology"},
    {"name": "Dr. Sarah Johnson", "specialty": "Pediatrics"},
    {"name": "Dr. David Brown", "specialty": "Orthopedics"},
    {"name": "Dr. Linda Martinez", "specialty": "Neurology"},
    {"name": "Dr. James Wilson", "specialty": "Gastroenterology"},
    {"name": "Dr. Patricia Lee", "specialty": "Endocrinology"},
    {"name": "Dr. Robert Taylor", "specialty": "Oncology"},
    {"name": "Dr. Barbara Anderson", "specialty": "Psychiatry"},
    {"name": "Dr. Christopher Thomas", "specialty": "Ophthalmology"}
]

appointment_times = [
    "12:00 PM on Wednesday, March 05, 2025",
    "04:30 PM on Wednesday, March 05, 2025",
    "02:15 PM on Wednesday, March 05, 2025",
    "10:00 AM on Thursday, March 06, 2025",
    "01:45 PM on Thursday, March 06, 2025",
    "11:30 AM on Friday, March 07, 2025",
    "03:00 PM on Friday, March 07, 2025",
    "09:30 AM on Monday, March 10, 2025",
    "02:00 PM on Monday, March 10, 2025",
    "10:45 AM on Tuesday, March 11, 2025"
]

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

def is_information_complete():
    return all([
        patient_info.name,
        patient_info.dob,
        patient_info.insurance_payer,
        patient_info.insurance_id,
        patient_info.chief_complaint,
        patient_info.address,
        patient_info.email,
        patient_info.phone,
        patient_info.appointment_time,
        patient_info.appointment_doctor
    ])


# these are highly subjective to how a normal conversatoin happens and are not using any nlp filters which can give use the best result. 
def update_patient_info(content: str):
    content = content.lower()

    # Name
    if "name is" in content:
        patient_info.name = re.search(r"name is (.+)", content).group(1).strip().title()

    # Date of Birth
    dob_match = re.search(r"(birth|born).*?(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", content)
    if dob_match:
        try:
            dob = datetime.strptime(dob_match.group(2), "%m/%d/%Y").date()
            patient_info.dob = dob.strftime("%Y-%m-%d")
        except ValueError:
            pass  # Invalid date format

    # Insurance
    if "insurance" in content:
        if "payer" in content:
            patient_info.insurance_payer = re.search(r"payer.*?is (.+)", content).group(1).strip().title()
        if "id" in content:
            patient_info.insurance_id = re.search(r"id.*?is (.+)", content).group(1).strip().upper()

    # Referral
    if "referral" in content:
        patient_info.referral = "yes" in content or "have" in content
        if patient_info.referral:
            physician_match = re.search(r"(doctor|dr\.?|physician).*?is (.+)", content)
            if physician_match:
                patient_info.referral_physician = physician_match.group(2).strip().title()

    # Chief Complaint
    complaint_keywords = ["reason", "visit", "complaint", "problem", "issue"]
    for keyword in complaint_keywords:
        if keyword in content:
            patient_info.chief_complaint = content.split(keyword)[-1].strip()
            break

    # Address
    if "address" in content:
        patient_info.address = re.search(r"address.*?is (.+)", content).group(1).strip().title()

    # Phone
    phone_match = re.search(r"\b(\d{3}[-.]?\d{3}[-.]?\d{4})\b", content)
    if phone_match:
        patient_info.phone = phone_match.group(1)

    # Email
    email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", content)
    if email_match:
        patient_info.email = email_match.group(0)

    # Appointment
    if "appointment" in content:
        time_match = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))", content)
        if time_match:
            patient_info.appointment_time = time_match.group(1)
        doctor_match = re.search(r"(doctor|dr\.?|physician).*?(\w+)", content)
        if doctor_match:
            patient_info.appointment_doctor = doctor_match.group(2).title()

    logger.info(f"Updated patient info: {patient_info}")
    
     # Offer available providers and times
    if is_information_complete() and not patient_info.appointment_time:
        available_doctors = ", ".join([doc["name"] for doc in random.sample(doctors, 3)])
        available_times = ", ".join(random.sample(appointment_times, 3))
        return f"Great! Based on your information, we have the following doctors available: {available_doctors}. And these appointment times: {available_times}. Which doctor and time would you prefer?"

    return None

def send_confirmation_email():
    msg = MIMEMultipart()
    msg['From'] = os.environ.get("SENDER_EMAIL")
    msg['To'] = patient_info.email
    msg['Subject'] = "Appointment Confirmation"
    
    body = f"Dear {patient_info.name},\n\nYour appointment with {patient_info.appointment_doctor} is scheduled for {patient_info.appointment_time}.\n\nBest regards,\nAssort Health"
    msg.attach(MIMEText(body, 'plain'))

    # Add your SMTP server details here
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(os.environ.get("SENDER_EMAIL"), os.environ.get("SENDER_PW"))
    text = msg.as_string()
    server.sendmail(msg['From'], msg['To'], text)
    server.quit()

    logger.info(f"Confirmation email sent to {msg['To']}")


async def entrypoint(ctx: JobContext):
    initial_ctx = llm.ChatContext().append(
        role="system",
        text=(
            "You are a voice assistant for Assort Health, scheduling patient appointments. "
            "You must collect the following information in a friendly, professional manner:\n"
            "1. Patient's name and date of birth\n"
            "2. Insurance information (payer name and ID)\n"
            "3. Referral information and physician name if applicable\n"
            "4. Chief medical complaint/reason for visit\n"
            "5. Demographics including address\n"
            "6. Contact information: phone number and email\n"
            "After collecting this information, offer available providers and appointment times. "
            "The call is not complete until all required information is collected and an appointment is scheduled, confirm this by saying the words appointment is scheduled."
            "Use short, concise responses suitable for voice interaction."
        ),
    )

    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Wait for the first participant to connect
    participant = await ctx.wait_for_participant()
    logger.info(f"starting voice assistant for participant {participant.identity}")

    # This project is configured to use Deepgram STT, OpenAI LLM and Cartesia TTS plugins
    # Other great providers exist like Cerebras, ElevenLabs, Groq, Play.ht, Rime, and more
    # Learn more and pick the best one for your app:
    # https://docs.livekit.io/agents/plugins
    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=deepgram.TTS(),
        turn_detector=turn_detector.EOUModel(),
        # minimum delay for endpointing, used when turn detector believes the user is done with their turn
        min_endpointing_delay=0.5,
        # maximum delay for endpointing, used when turn detector does not believe the user is done with their turn
        max_endpointing_delay=5.0,
        chat_ctx=initial_ctx,
    )

    usage_collector = metrics.UsageCollector()

    @agent.on("metrics_collected")
    def on_metrics_collected(agent_metrics: metrics.AgentMetrics):
        metrics.log_metrics(agent_metrics)
        usage_collector.collect(agent_metrics)
    
    @agent.on("user_speech_committed")
    def on_user_speech_committed(msg: llm.ChatMessage):
        response = update_patient_info(msg.content)
        if response:
            agent.say(response)

    @agent.on("agent_speech_committed")
    def on_agent_speech_committed(msg: llm.ChatMessage):
        if not is_information_complete():
            missing_fields = [field for field, value in asdict(patient_info).items() if value is None]
            agent.say(f"I still need to collect information about: {', '.join(missing_fields)}. Can you please provide that?")
        elif "scheduled" in msg.content.lower(): #having trouble in pin pointing the correct word to pick out the sentences to match for this
            send_confirmation_email()
            agent.say("Thank you for scheduling your appointment. You will receive a confirmation email shortly.")
    agent.start(ctx.room, participant)

    # The agent should be polite and greet the user when it joins :)
    await agent.say("Welcome to Assort Health. I'm here to help you schedule an appointment. Can you please provide your name and date of birth to start?", allow_interruptions=True)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name="assort-health-agent"
        ),
    )