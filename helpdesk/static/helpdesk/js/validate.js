//TODO: 'High Performing' is not a type of property -- will need to add an array of 'high performing' types.

/* Variables */

var key = {
    affordable_boolean: 'e_is_affordable_housing',
    affordable_list: 'e_type_affordable_housing',
    acp_list: 'e_acp_type',
    property_list: 'e_property_type',
    pathway_list: 'e_pathway',
};
var id = {
    affordable_boolean: '#id_' + key.affordable_boolean,
    affordable_list: '#id_' + key.affordable_list,
    acp_list: '#id_' + key.acp_list,
    property_list: '#id_' + key.property_list,
    pathway_list: '#id_' + key.pathway_list,
};
var group = {
    affordable_boolean: '#id_group_' + key.affordable_boolean,
    affordable_list: '#id_group_' + key.affordable_list,
    acp_list: '#id_group_' + key.acp_list,
};

/* Alerts */

var alertMsg1 = 'This property type is not eligible for the Standard Target Pathway, please select another pathway.';
var alertMsg2 = 'You have selected the Prescriptive Pathway, please note that DOEE will not approve this selection until the building owner has submitted an energy audit. For more information please see this FAQ [link to be provided later].';
var alertMsg3 = 'This property type is not eligible for the Extended Deep Energy Retrofit ACP Option, please select another pathway.'
var alertMsg4 = 'You have selected the Extended Deep Energy Retrofit ACP Option, please note that DOEE will not approve this selection until the building owner has submitted a Proposed Extended Deep Energy Retrofit Milestone Plan. For more information please see this FAQ [link to be provided later].'
var alertMsg5 = 'You have selected the Custom ACP Option, please note that DOEE will not approve this selection until the building owner has submitted custom ACP Option proposal. For more information please see this FAQ [link to be provided later].'

jQuery.validator.addMethod('alert1', function (value, element, param) {
    return this.optional(element) || !($(param.path).val() == 'Standard Target Pathway' && !($(param.prop).val() == '' || $(param.prop).val() == 'High Performing'));
}, alertMsg1);

jQuery.validator.addMethod('alert2', function (value, element) {
    var ok = this.optional(element) || value != 'Prescriptive Pathway';
    if(!ok) $(element).addClass("error-okay");
    else $(element).removeClass("error-okay");
    return ok;
}, alertMsg2);

/*  This field appears
    if "ACP Option" =  "Extended Deep Energy Retrofit"
    AND ("Affordable Housing/Rent Controlled?" = FALSE
    OR ("Primary Property Type - Portfolio Manager Calculated" != "College/University" OR "Hospital").
    If this alert text appears the user should not be able to submit the form, until they select another pathway */
jQuery.validator.addMethod('alert3', function (value, element, param) {
    return this.optional(element) || !( value == "Extended Deep Energy Retrofit" && ( !$(param.affordable).prop('checked') || ($(param.prop).val() != "College/University" || $(param.prop).val() != "Hospital")) );
}, alertMsg3);

/*   if "ACP Option" =  "Extended Deep Energy Retrofit"
    AND ("Affordable Housing/Rent Controlled?" = TRUE
    OR ("Primary Property Type - Portfolio Manager Calculated" = "College/University" OR "Hospital").
    If this alert text appears the user should not be able to submit the form, until they select another pathway */
jQuery.validator.addMethod('alert4', function (value, element, param) {
    return this.optional(element) || !( value == "Extended Deep Energy Retrofit" && ( $(param.affordable).prop('checked') || ($(param.prop).val() == "College/University" || $(param.prop).val() == "Hospital")) );
}, alertMsg4);

jQuery.validator.addMethod('alert5', function (value, element) {
    var ok =  this.optional(element) || value != 'Alternative Compliance Pathway';
    if(!ok) $(element).addClass("error-okay");
    else $(element).removeClass("error-okay");
    return ok;
}, alertMsg5);


/* Validations */

var form_validator = $('#ticket_submission_form').validate({
    ignore: '.error-okay',
    rules: {
        [key.pathway_list]: {
            alert2: true,
            alert5: true
        },
        [key.property_list]: {
            alert1: {
                param: {
                    path: id.pathway_list,
                    prop: id.property_list
                }
            }
        },
        [key.acp_list]: {
            alert3: {
                param: {
                    affordable: id.affordable_boolean,
                    prop: id.property_list
                }
            },
            alert4: {
                param: {
                    affordable: id.affordable_boolean,
                    prop: id.property_list
                }
            },
        }
    },
});


/* Hiding/showing elements based on other fields */

$(group.affordable_boolean).hide();
$(group.affordable_list).hide();
$(group.acp_list).hide();

$(id.property_list).change(function(){
    //Alert 3 must be checked when either of two fields changes
     if ($(id.acp_list).val() != '' && $(id.affordable_boolean).prop('checked'))
        form_validator.element(id.acp_list);

    //affordable_boolean field appears if the property type is Multifamily Housing
    if($(id.property_list).val() == "Multifamily Housing") {
        $(group.affordable_boolean).show();
    } else {
        $(group.affordable_boolean).hide();
        $(id.affordable_boolean).prop('checked', false);
    }

    //affordable_list field appears if "Primary Property Type - Portfolio Manager Calculated" = "Multifamily Housing" AND "Affordable Housing" = TRUE
    if($(id.property_list).val() == "Multifamily Housing" && $(id.affordable_boolean).prop('checked')) {
        $(group.affordable_list).show();
    } else {
        $(group.affordable_list).hide();
        $(id.affordable_list).val('');
    }
});

$(id.affordable_boolean).change(function(){
    //Alert 4 must be checked when either of two fields changes
    if ($(id.acp_list).val() != '' && $(id.property_list).val() != '')
        form_validator.element(id.acp_list);

    //affordable_list field appears if "Primary Property Type - Portfolio Manager Calculated" = "Multifamily Housing" AND "Affordable Housing" = TRUE
    if($(id.property_list).val() == "Multifamily Housing" && $(id.affordable_boolean).prop('checked')) {
        $(group.affordable_list).show();
    } else {
        $(group.affordable_list).hide();
        $(id.affordable_list).val('');
    }
});

$(id.pathway_list).change(function(){
    //removes class 'error-okay' so that validator will not ignore changes
    $(id.pathway_list).removeClass("error-okay");
    form_validator.element(id.pathway_list);

    //Alert 1 must be checked when either of two fields changes
    if ($(id.property_list).val() != '')
        form_validator.element(id.property_list);

    //acp_list field appears if "Pathway Selected" = "Alternative Compliance Pathway"
    if($(id.pathway_list).val() == "Alternative Compliance Pathway") {
        $(group.acp_list).show();
    } else {
        $(group.acp_list).hide();
        $(id.acp_list).val('');
    }
});
