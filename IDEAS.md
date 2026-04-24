

# A single intelligence system operating across model, infra and tools. 

## My thoughts 
For an intelligence system to operate autonomously, I believe it needs complete feedback loop. What to try next, hypothesis creation, given goal and existing public knowledge, system need to be able to generate new hypothesis. Second, try experiments on real world to validate the hypothesis and collect insights from experiments. Third, an orchestration engine to store the learnings generated as part of this process, and when to involve user in this process(E.g. my system kept failing on finding compilable code in trading domain, it need to involve user there)

## Idea#1 : Hypothesis generation engine. 
Finding new idea which will help us reach the goal is first and very important step. The model needs to have insights into what is the current domain and how things are working in this domain. I would expect a powerfull model would be trained on past hypothesis(research papers), experiment results, so it knows what is a good hypothesis looks like. 

So idea is, take past research papers, research results and subsequent papers which have done the experiments on it, and what kind of hypothesis these papers proposed, model will get trained on this data to understand what is a good hypothis look like. 

## Idea#2 : Going where ever users are
Research agents will be running over long periods, unlike coding writing usecases, research agents need to run longer periods, most likely days. So the orchestration engine need to be running somewhere in cloud. Moreover Human input will be important in guiding the agent in right direction. User need to be able to interact with the system from multiple entry points. 

Idea is to build a single system which aggregates user inputs/outputs across different channels. E.g. agent posts a summary of experiments and asks user for specific question, this information need to be shared in a slak channel to user and user can respond from mobile devices, and agent can continue the research. 

## Idea#3 : Orchstration engine
A overall orchestration engine which cordinates across multiple systems, keeping track of experiment results, model memories, results, user interactions, running experiments, interaction with physical systems. 

I am more excited applying these ideas on a real world scenario. I have beeen working on algorthmic trading and running experiments using Quant Connect platform. My manual process starts with having a hypothesis, "like there is a big sell order, there will be crowd affect and price will go down". I used to hand write the QC code for this and run backtest, analyze the results and see if it good or if we have too many indicators, does it work in live trading etc. With advent of LLMs, it shortened the loop, as I can go to QC code quickly from hypothesis. But still need to run the experiments and analysis manually. With agentic feedback, I am excited about how I can close the gap. Hypothesis -> GC experiment -> Analyze results -> Go back. 

I gave initial goal to avoid agent searching the problem space randmly and gave guard rails.
Goal: I am interested in CL rising or dropping 1%, analyze data before these events and predict the events occuring. 
Guard rails: For now I am using only price and volume data only, Having alternative data like shipping container location live and historical data, will give edge. 

