python manage.py makemessages -i venv -i data
pushd helpdesk
python ../manage.py compilemessages --locale fi
popd
