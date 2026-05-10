

from core.worker_agent import WorkerAgent, load_config

def main():
    config = load_config()
    agent = WorkerAgent(config)
    agent.run()


if __name__ == "__main__":
    main()