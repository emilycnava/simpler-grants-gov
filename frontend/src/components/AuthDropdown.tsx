import { useTranslations } from "next-intl";

const AuthDropdown = () => {
  const t = useTranslations("Header");

  return (
    <ul className="usa-nav__secondary usa-accordion">
      <li className="usa-nav__primary-item">
        <a className="usa-nav__link usa-current">
          <div>{t('sign_in')}</div>
        </a>
      </li>
    </ul>
  );
};

export default AuthDropdown;
