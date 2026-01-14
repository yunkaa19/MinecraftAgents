from abc import ABC, abstractmethod


class MiningStrategy(ABC):
    @abstractmethod
    def execute(self, agent):
        """
        Execute the mining strategy.
        :param agent: The agent instance executing the strategy.
        """
        pass


class BuildingStrategy(ABC):
    @abstractmethod
    def execute(self, agent, location):
        """
        Execute the building strategy at the given location.
        :param agent: The agent instance.
        :param location: Tuple (x, y, z) where the building should start.
        """
        pass

    @abstractmethod
    def get_bom(self):
        """
        Return the Bill of Materials required for this build.
        :return: Dictionary of material names and counts.
        """
        pass


class ExplorationStrategy(ABC):
    @abstractmethod
    def execute(self, agent):
        """
        Execute the exploration strategy.
        :param agent: The agent instance.
        :return: A dictionary of exploration data (e.g., {'flat_spots': [...]}) or None.
        """
        pass
