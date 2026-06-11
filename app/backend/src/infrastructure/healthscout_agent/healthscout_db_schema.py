class Trasportation:
    def __init__(self, telephone_number: str, provider: str):
        self.telephone_number = telephone_number
        self.provider = provider


class Doctor:
    def __init__(self, managed_care_plan: str, first_name: str, last_name: str, phone: str, address: str, pri_spec: str, transportation: Trasportation):
        self.insurance = managed_care_plan
        self.first_name = first_name
        self.last_name = last_name
        self.phone = phone
        self.address = address
        self.specialty = pri_spec
        self.transportation = transportation

    def __check_attribute(self, value):
        # Returns the value if it is valid. Else specific message
        result = None

        if value is not None:
            result = value
        elif value is None:
            result = "I don't have this info in my DB."

        return result

    def to_string(self):
        return f"""
- Doctor: {self.__check_attribute(self.first_name)} {self.__check_attribute(self.last_name)}
  - Doctor Phone Number: {self.__check_attribute(self.phone)}
  - Specialization: {self.__check_attribute(self.specialty)}
  - Address: {self.__check_attribute(self.address)}
  - Insurance: {self.__check_attribute(self.insurance)}
- Transportation :
    - Provider: {self.__check_attribute(self.transportation.provider)}
    - Phone: {self.__check_attribute(self.transportation.telephone_number)}
"""