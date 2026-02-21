from groq import Groq
# import CodeC_helpers
import re
import json
import utils


def agent_sim(model_LLM, plan_sys_prompt, user_query):
  # Add your Groq API key here (get one for free at https://console.groq.com/keys)
  api_key = "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"  # Replace with your actual API key

  client = Groq(api_key=api_key)
  completion = client.chat.completions.create(
      model= model_LLM, #"llama-3.1-8b-instant", #"llama-3.3-70b-versatile",
      messages=[
          {
              "role": "system",
              "content": plan_sys_prompt  # Your system prompt here
          },
        {
          "role": "user",
          "content": user_query          
        },
      ],
      temperature=1,
      max_completion_tokens=1024,
      top_p=1,
      stream=True,
      stop=None
  )
  response_content = ""
  for chunk in completion:
      chunk_content = chunk.choices[0].delta.content or ""
      response_content += chunk_content
      # print(chunk_content, end="")  # Optional: Still print to console if you want to see it live
  return response_content

#### ---- interaction 1 code ---- ####

with open("sys_prompt.txt", "r") as f:
    plan_sys_prompt = f.read()

init_model = "meta-llama/llama-4-scout-17b-16e-instruct"    

role = "Anagha"  # or "agent2" depending on which agent is speaking
user_query = "Hi I am Anagha, who are you? How do you do? What is your favorite hobby?"

# Create the JSON object
log_entry = json.dumps({"role": role, "content": user_query})

with open("../conversational_history.txt", "w", encoding="utf-8") as f:
    f.write(log_entry + "\n")

#### ---- interaction 2 code ---- ####

role = "Gaurav"  # or "agent2" depending on which agent is speaking
agent_resp = agent_sim(init_model, plan_sys_prompt, user_query)

# Create the JSON object
log_entry = json.dumps({"role": role, "content": agent_resp})

# Append to file
with open("../conversational_history.txt", "a", encoding="utf-8") as f:
    f.write(log_entry + "\n")