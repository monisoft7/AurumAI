from core.config import settings


def main():

    print("=" * 50)
    print(settings.APP_NAME)
    print("Version:", settings.VERSION)
    print("=" * 50)


if __name__ == "__main__":
    main()
