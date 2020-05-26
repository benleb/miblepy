"""Library for body metrics calculation.

Credits for this file go to @lolouk44!
All these crazy magic numbers are reverse-engineered from the
Mi Body Composition Scale's library by him. Thanks!
"""

from math import floor
from typing import List, Union


LIMIT_AGE = 150
LIMIT_HEIGHT = 250
LIMIT_WEIGHT = 300
LIMIT_IMPEDANCE = 3000

# from mi fit
BMI_SCALE = [18.5, 25, 28, 32]


class BodyMetrics:
    def __init__(self, weight: float, height: int, age: int, sex: str, impedance: int):
        self.weight = weight
        self.height = height
        self.age = age
        self.sex = sex
        self.impedance = impedance

        # Check for potential out of boundaries
        if self.height > LIMIT_HEIGHT:
            raise ValueError(f"Height too high ({self.height} > LIMIT_HEIGHT)")

        if self.weight < 1 or weight > LIMIT_WEIGHT:
            raise ValueError(f"Weight too low/high (1kg > {self.weight} > {LIMIT_WEIGHT})")

        if self.age > LIMIT_AGE:
            raise ValueError(f"Age too high ({self.age} > {LIMIT_AGE})")

        # if self.impedance > LIMIT_IMPEDANCE:
        #     raise ValueError(f"Impedance too high ({self.impedance} > {LIMIT_IMPEDANCE})")

    # set the value to a boundary if it overflows
    @staticmethod
    def check_bounds(
        value: Union[int, float], minimum: Union[int, float], maximum: Union[int, float]
    ) -> Union[int, float]:
        if value < minimum:
            return minimum

        if value > maximum:
            return maximum

        return value

    # lean body mass coefficient (with impedance)
    def get_lbm_coefficient(self) -> Union[int, float]:
        lbm = (self.height * 9.058 / 100) * (self.height / 100)
        lbm += self.weight * 0.32 + 12.226
        lbm -= self.impedance * 0.0068
        lbm -= self.age * 0.0542
        return lbm

    # basal metabolism rate(?)
    def get_bmr(self) -> Union[int, float]:
        if self.sex == "female":
            bmr = 864.6 + self.weight * 10.2036
            bmr -= self.height * 0.39336
            bmr -= self.age * 6.204
            bmr = bmr if bmr <= 2996 else 5000
        elif self.sex == "male":
            bmr = 877.8 + self.weight * 14.916
            bmr -= self.height * 0.726
            bmr -= self.age * 8.976
            bmr = bmr if bmr <= 2322 else 5000
        else:
            raise ValueError(f"Sex should be male or female but is {self.sex}")

        return self.check_bounds(bmr, 500, 10000)

    # Get fat percentage
    def getFatPercentage(self) -> Union[int, float]:
        # Set a constant to remove from LBM
        if self.sex == "female" and self.age <= 49:
            const = 9.25
        elif self.sex == "female" and self.age > 49:
            const = 7.25
        else:
            const = 0.8

        # Calculate body fat percentage
        LBM = self.get_lbm_coefficient()

        if self.sex == "male" and self.weight < 61:
            coefficient = 0.98
        elif self.sex == "female" and self.weight > 60:
            coefficient = 0.96
            if self.height > 160:
                coefficient *= 1.03
        elif self.sex == "female" and self.weight < 50:
            coefficient = 1.02
            if self.height > 160:
                coefficient *= 1.03
        else:
            coefficient = 1.0

        fatPercentage = (1.0 - (((LBM - const) * coefficient) / self.weight)) * 100

        # Capping body fat percentage
        if fatPercentage > 63:
            fatPercentage = 75

        return self.check_bounds(fatPercentage, 5, 75)

    # Get water percentage
    def getWaterPercentage(self) -> Union[int, float]:
        waterPercentage = (100 - self.getFatPercentage()) * 0.7

        if waterPercentage <= 50:
            coefficient = 1.02
        else:
            coefficient = 0.98

        # Capping water percentage
        if waterPercentage * coefficient >= 65:
            waterPercentage = 75

        return self.check_bounds(waterPercentage * coefficient, 35, 75)

    # bone mass
    def getBoneMass(self) -> Union[int, float]:
        if self.sex == "female":
            base = 0.245691014
        else:
            base = 0.18016894

        boneMass = (base - (self.get_lbm_coefficient() * 0.05158)) * -1

        if boneMass > 2.2:
            boneMass += 0.1
        else:
            boneMass -= 0.1

        # Capping boneMass
        if self.sex == "female" and boneMass > 5.1:
            boneMass = 8
        elif self.sex == "male" and boneMass > 5.2:
            boneMass = 8
        return self.check_bounds(boneMass, 0.5, 8)

    # Get muscle mass
    def getMuscleMass(self) -> Union[int, float]:
        muscleMass = self.weight - ((self.getFatPercentage() * 0.01) * self.weight) - self.getBoneMass()

        # Capping muscle mass
        if self.sex == "female" and muscleMass >= 84:
            muscleMass = 120
        elif self.sex == "male" and muscleMass >= 93.5:
            muscleMass = 120

        return self.check_bounds(muscleMass, 10, 120)

    # Get Visceral Fat
    def getVisceralFat(self) -> Union[int, float]:
        if self.sex == "female":
            if self.weight > (13 - (self.height * 0.5)) * -1:
                subsubcalc = ((self.height * 1.45) + (self.height * 0.1158) * self.height) - 120
                subcalc = self.weight * 500 / subsubcalc
                vfal = (subcalc - 6) + (self.age * 0.07)
            else:
                subcalc = 0.691 + (self.height * -0.0024) + (self.height * -0.0024)
                vfal = (((self.height * 0.027) - (subcalc * self.weight)) * -1) + (self.age * 0.07) - self.age
        else:
            if self.height < self.weight * 1.6:
                subcalc = ((self.height * 0.4) - (self.height * (self.height * 0.0826))) * -1
                vfal = ((self.weight * 305) / (subcalc + 48)) - 2.9 + (self.age * 0.15)
            else:
                subcalc = 0.765 + self.height * -0.0015
                vfal = (((self.height * 0.143) - (self.weight * subcalc)) * -1) + (self.age * 0.15) - 5.0

        return self.check_bounds(vfal, 1, 50)

    # Get BMI
    def getBMI(self) -> Union[int, float]:
        return self.check_bounds(self.weight / ((self.height / 100) * (self.height / 100)), 10, 90)

    # Get ideal weight (just doing a reverse BMI, should be something better)
    def getIdealWeight(self) -> Union[int, float]:
        return self.check_bounds((22 * self.height) * self.height / 10000, 5.5, 198)

    # Get ideal weight scale (BMI scale converted to weights)
    def getIdealWeightScale(self) -> List[Union[int, float]]:
        scale = []
        for bmiScale in BMI_SCALE:
            scale.append((bmiScale * self.height) * self.height / 10000)
        return scale

    # Get protetin percentage (warn: guessed formula)
    def getProteinPercentage(self) -> Union[int, float]:
        proteinPercentage = 100 - (floor(self.getFatPercentage() * 100) / 100)
        proteinPercentage -= floor(self.getWaterPercentage() * 100) / 100
        proteinPercentage -= floor((self.getBoneMass() / self.weight * 100) * 100) / 100
        return proteinPercentage
