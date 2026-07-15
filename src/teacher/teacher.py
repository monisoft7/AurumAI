from teacher.lessons import LESSONS


class Teacher:

    def teach(self):

        for lesson in LESSONS:

            print(f"Teaching: {lesson}")


if __name__ == "__main__":

    Teacher().teach()